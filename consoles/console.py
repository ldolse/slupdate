import os
from dat import RomDat
from softwarelist import SoftwareList, Part
from utils import select_directory
from rom_management import ZipProcessor, CHD
from rom_management.processing import ProcessManager
from rom_management.exceptions import (
    HandlerException,
    UserActionRequiredException,
    SkipCurrentItemException,
)
from optical_media.utils import OpticalMediaProcessor
from rom_management.handlers import registry, SpecialHandler
from media_registry import MediaRegistry, CDMedia
from game_metadata import RedumpDB
from collections import OrderedDict
from .platform_state import PlatformState

from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from consoles.platform_manager import PlatformManager
    from dat import RomDat


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
        self.process_manager = ProcessManager(self)

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

        # Recreate process manager with reset state
        self.process_manager = ProcessManager(self)

    def get_relevant_handlers(
        self, media: CDMedia, file_data: OpticalMediaProcessor
    ) -> List[SpecialHandler]:
        """Get all relevant handlers for a media item"""
        return self.handler_registry.get_relevant_handlers(media, file_data)

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

    def start_validation_process(self) -> dict:
        """Start the validation process through ProcessManager"""
        if not self.process_manager:
            raise Exception("ProcessManager not initialized")

        # Initialize handlers for the process manager
        self.process_manager.initialize_handlers()

        from rom_management.processing.archive_validation import (
            ArchiveValidationProcess,
        )

        return self.process_manager.start_process(ArchiveValidationProcess)

    def start_chd_build_process(self) -> dict:
        """Start the CHD build process through ProcessManager"""
        if not self.process_manager:
            raise Exception("ProcessManager not initialized")
        return self.process_manager.start_chd_build()

    def validate_matched_entries(self) -> None:
        """
        Validate zip files for all matched entries in MediaRegistry
        Skip validation if media signature is already in validated state
        """
        if not self.mr:
            print("MediaRegistry not initialized")
            return

        zip_processor = ZipProcessor()

        for media in self.mr.media_directory.keys():
            zip_path = None
            # Skip if this media signature is already validated
            media_sig = media.sha1_signature or media.crc_signature
            if media_sig in self.state.matched_media_sigs:
                print(
                    f". ✅ {media.dat_game_entry.name} already validated, skipping zip check"
                )
                # Add to matched_buildable_media since we know it's valid
                self.matched_buildable_media[media] = None
                continue

            if not media.dat_game_entry.name:
                print(f"  ⚠️  Media ID: {media.id} - skipping, No DAT Game name")
                continue

            if media.dat_game_entry is None or media.softlist_part is None:
                print(
                    f"  ⚠️  {media.dat_game_entry.name}: Skipping - No valid DAT game entry or softlist part reference"
                )
                continue

            # Find ROM directory for this DAT
            rom_dir = media.dat_game_entry.dat.rom_path
            if not os.path.isdir(rom_dir):
                print(
                    f"  ⚠️  {media.dat_game_entry.name}: Skipping - ROM directory does not exist: {rom_dir}"
                )
                continue
            from rom_management.archive import MD5ScanRequiredException

            try:
                # Find and validate zip
                zip_path = zip_processor.find_valid_zip(media.dat_game_entry, rom_dir)
            except MD5ScanRequiredException:
                user_input = (
                    input(
                        f"   {media.dat_game_entry.name} requires full scan, Check Using MD5 (slow)? (y/n): "
                    )
                    .strip()
                    .lower()
                )
                if user_input != "y":
                    continue
                else:
                    zip_path = zip_processor.find_valid_zip(
                        media.dat_game_entry, rom_dir, md5=True
                    )

            if zip_path is not None:
                print(f"  ✅ Found valid zip: {media.dat_game_entry.name}")
                media.zip_path = zip_path
                self.matched_buildable_media[media] = (
                    None  # Value doesn't matter, using key as an ordered set
                )
            else:
                print(f"  ⚠️  {media.dat_game_entry.name}: No valid zip found")
                continue

    def build_chds_for_matched(self) -> dict:
        """
        Convert all matched entries in MediaRegistry to CHD format.
        Returns navigation info with payload if exception occurs
        """
        for media in self._media_to_process:
            # Check if CHD already exists and is validated
            title = (
                media.softlist_part.part_of.name
                if media.softlist_part and media.softlist_part.part_of
                else None
            )
            if not title:
                print(
                    f"  ⚠️ Skipping - No valid softlist part or title for media ID {media.id}"
                )
                continue

            # Check if this CHD is already validated
            expected_chd_path = os.path.join(
                self.chd_path, title, f"{media.softlist_part.disk_name}.chd"
            )
            if expected_chd_path in self.state.validated_chds_paths and os.path.exists(
                expected_chd_path
            ):
                existing_chd = CHD(chd_path=expected_chd_path)
                if existing_chd.is_valid:
                    print(
                        f"✅ CHD already validated for {media.dat_game_entry.name}, skipping"
                    )
                    self.validated_chds.add(existing_chd)
                    continue
                else:
                    # will try to rebuild if it's not reported as valid
                    os.remove(expected_chd_path)

            elif os.path.exists(expected_chd_path):
                matched_chd = CHD(chd_path=expected_chd_path)
                print(
                    f"⚠️  CHD already exists for {media.dat_game_entry.name} at {expected_chd_path}"
                )

                # Create exception with existing version info
                from rom_management.exceptions import CHDAlreadyExistsException

                existing_version = (
                    matched_chd._get_chd_info().get("file_version")
                    if matched_chd.is_valid
                    else None
                )
                exception = CHDAlreadyExistsException(
                    expected_chd_path, existing_version
                )

                # Return navigation info with exception as payload
                return {"menu": "existing_chd_menu", "payload": exception}

            file_data = OpticalMediaProcessor(media, tmpdsk=self.pm.tmpdsk)

            try:
                # initialize CHD object
                print(f"Converting {media.zip_path} to CHD")
                print(f"  softlist title: {title}")

                # Extract the ROM to a temp directory
                file_data.extract_and_process()

                if not file_data.temp_dir.exists():
                    raise Exception(
                        f"Temp directory creation for {media.dat_game_entry.name} failed"
                    )

                # Get and apply handlers
                handlers = self.get_relevant_handlers(media, file_data)

                for handler in handlers:
                    try:
                        result = handler.handle(media, file_data)
                        if not result.get("success", True):
                            raise HandlerException(
                                f"Handler {handler.name} failed: {result.get('error')}"
                            )
                    except SkipCurrentItemException:
                        print(f"Skipping item due to handler request")
                        continue
                    except UserActionRequiredException as e:
                        # Return navigation info with exception as payload
                        return {"menu": "handler_error_menu", "payload": e}

                # Prepare for CHD conversion
                toc_source = file_data.current_toc

                matched_chd = CHD(
                    source=media, base_path=self.chd_path, toc_source=toc_source
                )

                if matched_chd.exists and matched_chd.is_valid:
                    self.validated_chds.add(matched_chd)
                    self.state.add_validated_chd_path(matched_chd.path)
                    print(f"✅ Converted {media.zip_path} to CHD")

            except HandlerException as e:
                # Return navigation info with exception as payload
                return {"menu": "handler_error_menu", "payload": e}
            except Exception as e:
                print(f"Unexpected error processing {media.dat_game_entry.name}: {e}")
                continue
            finally:
                # Clean up temp directory only if we're not retrying
                if "file_data" in locals() and file_data:
                    file_data.cleanup()

        # Return success navigation if all processing completes
        return {"menu": "chd_build_menu", "payload": None}
