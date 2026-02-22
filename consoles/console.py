import os
from dat import RomDat
from softwarelist import SoftwareList, Part
from utils import select_directory
from rom_management import ZipProcessor, CHD
from optical_media.utils import OpticalMediaProcessor
from rom_management.handlers import registry, SpecialHandler
from media_registry import MediaRegistry, CDMedia
from game_metadata import RedumpDB
from collections import OrderedDict
from .platform_state import PlatformState

from typing import TYPE_CHECKING, Optional, List, Any, Tuple

if TYPE_CHECKING:
    from consoles.platform_manager import PlatformManager
    from dat import RomDat
    from rom_management.processing.models import ResultObject


class Platform:
    def __init__(self, key: str, name: str, softlist_xml_path: str, chd_path: str):
        """
        Initialize a Platform object.
        :param key: Unique identifier for the platform (e.g., 'psx')
        :param name: User-friendly name for the platform (e.g., 'Sony Playstation')
        :param softlist_xml_path: Path to the MAME software list XML file
        """
        self.key = key
        self.name = name
        self.pm: PlatformManager = None
        self.softlist_xml_path = softlist_xml_path
        self.chd_path = chd_path
        self.softwarelist: SoftwareList = None
        self.dat_directories: dict[str, list[RomDat]] = {}
        self.redump_db: RedumpDB = None
        self.mr: MediaRegistry = None
        self.matched_buildable_media: OrderedDict[CDMedia, None] = OrderedDict()
        self.validated_chds: set[CHD] = set()
        self._chd_handling_preference = (
            None  # Can be "ask", "overwrite", or "skip", set via Exception
        )
        self._chd_build_index = 0
        self.handler_registry = registry
        self.state = PlatformState()

    def save_state(self) -> PlatformState:
        """Save current state to PlatformState object"""
        # Update directory status and sync with current dat_directories keys
        self.state.dat_directories = list(
            self.dat_directories.keys()
        )  # Sync with current keys

        # Update processing state
        self.state._chd_build_index = self._chd_build_index

        # Update matched media signatures
        self.state.matched_media_sigs = [
            media.sha1_signature or media.crc_signature
            for media in self.matched_buildable_media.keys()
        ]

        # Update CHD handling preference
        self.state._chd_handling_preference = self._chd_handling_preference

        # Update validated CHD paths
        self.state.validated_chds_paths = [chd.path for chd in self.validated_chds]

        # Save Redump DB if it exists
        if self.redump_db:
            self.state.redump_db = self.redump_db.to_dict()

        return self.state

    def load_state(self, state: PlatformState):
        """Load state from PlatformState object"""
        self.state = state

        # restore dat directories
        for path in self.state.dat_directories:
            if path not in self.dat_directories:
                self.dat_directories[path] = []

        # Restore processing state
        self._chd_build_index = self.state._chd_build_index
        self._chd_handling_preference = self.state._chd_handling_preference

    def reset(self) -> None:
        """Reset platform state while preserving DAT directories"""
        # Save current dat_directories
        saved_dat_dirs = self.dat_directories.copy()

        # Reset state by creating new PlatformState with preserved dat_directories
        self.state = PlatformState()
        self.state.dat_directories = list(saved_dat_dirs.keys())

        # Reset all other attributes to initial state
        self.softwarelist = None
        self.redump_db = None
        self.mr = None
        self.matched_buildable_media = OrderedDict()
        self.validated_chds = set()
        self._chd_handling_preference = None
        self._chd_build_index = 0

    def get_relevant_handlers(
        self, media: CDMedia, file_data: Any = None, process: Any = None
    ) -> Tuple[List[SpecialHandler], Optional["ResultObject"]]:
        """Get all relevant handlers for a media item"""
        return self.handler_registry.get_relevant_handlers(media, file_data, process)

    @property
    def _media_to_process(self) -> list[CDMedia]:
        return list(self.matched_buildable_media.keys())[self._chd_build_index :]

    @property
    def _all_dats(self) -> list[RomDat]:
        """Flatten all DAT instances across directories."""
        return [dat for dats_list in self.dat_directories.values() for dat in dats_list]

    @property
    def total_parts(self):
        return sum(len(e.parts) for e in self.softwarelist.software_items)

    @property
    def chd_handling_preference(self) -> str:
        return self._chd_handling_preference

    def set_chd_preference(self, preference: str) -> None:
        """
        Set the CHD handling preference for this platform.

        Args:
            preference: One of "ask", "overwrite", "skip"
        """
        valid_preferences = ["ask", "overwrite", "skip"]
        if preference not in valid_preferences:
            raise ValueError(
                f"Invalid preference: {preference}. Must be one of {valid_preferences}"
            )
        self._chd_handling_preference = preference

    @property
    def total_softlist_entries(self) -> int:
        """Total number of software list entries (titles)"""
        return len(self.softwarelist.software_items)

    @property
    def total_source_ref(self) -> int:
        """Total number of individual discs that contain source references"""
        count = 0
        for entry in self.softwarelist.software_items:
            for part in entry.parts:
                if hasattr(part, "game_entry") and part.game_entry is not None:
                    count += 1
        return count

    @property
    def total_source_found(self) -> int:
        """Number of software list entries that have at least one part with a source match"""
        count = 0
        for entry in self.softwarelist.software_items:
            if any(hasattr(part, "matched") and part.matched for part in entry.parts):
                count += 1
        return count

    @property
    def total_source_dat(self) -> int:
        """Number of parts that have a 'source_dat' entry (matched to DAT)"""
        count = 0
        for entry in self.softwarelist.software_items:
            for part in entry.parts:
                if hasattr(part, "matched") and part.matched:
                    count += 1
        return count

    @property
    def all_parts(self) -> List:
        """All parts that have a 'source_dat' entry (matched to DAT)"""
        matched = []
        for entry in self.softwarelist.software_items:
            for part in entry.parts:
                if hasattr(part, "matched") and part.matched:
                    matched.append(part)
        return matched

    @property
    def chd_count(self) -> int:
        """Number of CHDs that have been validated"""
        return len(self.validated_chds)

    @property
    def total_source_rom(self) -> int:
        """Number of parts that have a valid zip file"""
        return len(self.matched_buildable_media)

    def get_source_stats(self) -> dict:
        """
        Builds a dictionary with the total number of dumps attributed to each source group.

        Returns:
            dict: A dictionary with the total number of dumps per source group
        """
        from collections import defaultdict

        counts = defaultdict(int)

        for entry in self.softwarelist.software_items:
            for part in entry.parts:
                if hasattr(part, "source_group") and part.source_group:
                    counts[part.source_group] += 1

        return dict(counts)

    def print_source_stats(self):
        """
        Prints the source group statistics as percentages.
        Uses total_source_ref as the denominator for percentage calculations.
        """
        stats = self.get_source_stats()
        known_sum = 0
        print("Details by DAT Group:")
        for group, count in stats.items():
            known_sum += count
            percentage = (
                (count / self.total_source_ref) * 100
                if self.total_source_ref > 0
                else 0
            )
            print(f"  {group}: {percentage:.1f}%")

        if self.total_source_ref > 0:
            other_percent = (
                (self.total_source_ref - known_sum) / self.total_source_ref
            ) * 100
            print(f"  Unknown: {other_percent:.1f}%")
        else:
            print("  No source references found")
        print("\n")

    def register_dat_media(self) -> None:
        self.update_dats()
        self.mr = MediaRegistry(self.key)
        for dat_instance in self._all_dats:
            dat_instance.register_to_media_registry(self.mr)

    def register_softlist(self) -> None:
        self.softwarelist = SoftwareList.from_file(self.softlist_xml_path)
        self.softwarelist.extract_source_data()
        self.softwarelist.register_to_media_registry(self.mr)

    def _init_redump_db(self) -> None:
        if self.redump_db == None:
            self.redump_db = RedumpDB(self.key)
        self.redump_db.fetch_all

    def process_data(self) -> None:
        """
        Wrapper function to run all necessary setup steps for mapping.
        This orchestrates the initial data processing pipeline.
        """
        self.update_dats()  # find all DAT files and assign ROM directories
        self.register_dat_media()  # register all DAT files to MediaRegistry
        self.register_softlist()  # load and register software list to MediaRegistry
        self.print_stats()

    def print_stats(self, zip=False, chd=False):
        # Print statistics after processing
        print(
            f"found:\n  {self.total_source_ref} / {self.total_parts} individual discs contain source references"
        )
        print(
            f"  {self.total_source_dat} individual discs can be matched to dat sources"
        )
        print(
            f"  {self.total_source_found} / {self.total_softlist_entries} Software List Entries have DAT matches"
        )
        if zip:
            print(f"  {self.total_source_rom} valid zip files")
        if chd:
            print(
                f"  {self.chd_count} chds already exist in the destination directory\n"
            )
        print("\n")
        self.print_source_stats()

    def update_dats(self):
        """
        Process all DAT files under `dat_directory_path`, creating DAT instances and assigning ROM directories.
        - For RomVault: Maps based on directory structure + DAT metadata name
        - For manual mode: User selects a single ROM directory for each DAT
        """
        for dat_directory_path in self.dat_directories.keys():
            if not os.path.exists(dat_directory_path) or not os.path.isdir(
                dat_directory_path
            ):
                print(
                    f"Directory `{dat_directory_path}` does not exist or is not a directory."
                )
                continue

            dat_files = [
                f
                for f in sorted(os.listdir(dat_directory_path))
                if f.endswith(".xml") or f.endswith(".dat")
            ]

            # RomVault: Generate base ROM directory from DAT dir
            rom_dir_base = dat_directory_path.replace(
                self.pm.datroot, self.pm.romroot, 1
            )

            dats_in_dir = []

            for file_name in sorted(dat_files):
                full_path = os.path.join(dat_directory_path, file_name)

                # Skip DAT files that can't be parsed (e.g., non-XML .dat files)
                try:
                    dat = RomDat.from_file(full_path)
                except Exception as e:
                    print(f"Skipping invalid DAT {file_name}: {e}")
                    continue

                if self.pm.romvault and len(dat_files) > 1:
                    # check subdirectory based on DAT metadata name
                    rom_subdir = os.path.join(rom_dir_base, dat.name)
                    dat.rom_path = rom_subdir
                    if not os.path.exists(rom_subdir):
                        print(
                            f"RomVault subdirectory `{rom_subdir}` does not exist. ROM files can be added later."
                        )
                else:
                    # Use the base ROM directory for single DATs or manual mode
                    if self.pm.romvault:
                        dat.rom_path = rom_dir_base
                        if not os.path.exists(rom_dir_base):
                            print(
                                f"RomVault directory `{rom_dir_base}` does not exist. ROM files can be added later."
                            )
                    elif not self.pm.romvault:
                        prompt_msg = f"Select ROM directory for DAT: {file_name}"
                        rom_subdir = select_directory(
                            prompt_msg, start_dir=self.pm.romroot
                        )
                        dat.rom_path = rom_subdir

                dats_in_dir.append(dat)

            self.dat_directories[dat_directory_path] = dats_in_dir

    def map_redump_urls(self) -> list[Part]:
        self._init_redump_db()
        match_failures = []
        url_parts = self.softwarelist.unmatched_redump_url_parts
        redump_base = "http://redump.org"
        for part in url_parts:
            url = part.redump_url.replace(redump_base, "")
            if url in self.redump_db.entries_by_url:
                entry = self.redump_db.entries_by_url[url]
                hashkey = self.redump_db.entries_by_url[url].site_hash
                if hashkey in self.mr.media_hashes:
                    dat_entry_name = self.mr.media_hashes[hashkey].dat_game_entry.name
                    print(
                        f"✅ Matched existing media: {part.part_of.name} to {dat_entry_name}"
                    )
                    if part.game_entry is not None:
                        print(
                            "    [Info] replacing existing source references for this part"
                        )
                    part.game_entry = self.mr.media_hashes[hashkey].dat_game_entry
                    part.cdmedia = self.mr.media_hashes[hashkey]
            else:
                print(f"{part.redump_url} no longer in redump, removing reference")
                part.redump_url = ""
                match_failures.append(part)
        return match_failures
