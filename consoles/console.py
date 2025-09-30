#from modules.dat import DAT
import os
from dat import RomDat
from softwarelist import SoftwareList, Part
from utils.utils import select_directory
from rom_management import ZipProcessor, CHD
from media_registry import MediaRegistry, CDMedia
from game_metadata import RedumpDB

from typing import TYPE_CHECKING, Optional
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
        self.matched_buildable_media: list[CDMedia] = []
        self.validated_chds: set[CHD] = set()
        self._chd_handling_preference = "ask"  # Can be "ask", "overwrite", or "skip"
        self._chd_build_index = 0

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

    def register_dat_media(self) -> None:
        self.update_dats()
        self.mr = MediaRegistry()
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
        self.update_dats() # find all DAT files and assign ROM directories
        self.register_dat_media() # register all DAT files to MediaRegistry
        self.register_softlist() # load and register software list to MediaRegistry

    def update_dats(self):
        """
        Process all DAT files under `dat_directory_path`, creating DAT instances and assigning ROM directories.
        - For RomVault: Maps based on directory structure + DAT metadata name
        - For manual mode: User selects a single ROM directory for each DAT
        """
        for dat_directory_path in self.dat_directories.keys():
            if not os.path.exists(dat_directory_path) or not os.path.isdir(dat_directory_path):
                print(f"Directory `{dat_directory_path}` does not exist.")
                return

            dat_files = [f for f in sorted(os.listdir(dat_directory_path))
                        if f.endswith(".xml") or f.endswith(".dat")]

            # RomVault: Generate base ROM directory from DAT dir
            rom_dir_base = dat_directory_path.replace(self.pm.datroot, self.pm.romroot, 1)

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
                    if not os.path.exists(rom_subdir):
                        print(f"RomVault subdirectory `{rom_subdir}` does not exist.")
                        continue
                    dat.rom_path = rom_subdir
                else:
                    # Use the base ROM directory for single DATs or manual mode
                    if self.pm.romvault and os.path.exists(rom_dir_base):
                        dat.rom_path = rom_dir_base
                    elif not self.pm.romvault:
                        prompt_msg = f"Select ROM directory for DAT: {file_name}"
                        rom_subdir = select_directory(prompt_msg, start_dir=self.pm.romroot)
                        dat.rom_path = rom_subdir

                dats_in_dir.append(dat)

            self.dat_directories[dat_directory_path] = dats_in_dir

    def map_redump_urls(self) -> list[Part]:
        self._init_redump_db()
        match_failures = []
        url_parts = self.softwarelist.unmatched_redump_url_parts
        redump_base = 'http://redump.org'
        for part in url_parts:
            url = part.redump_url.replace(redump_base,'')
            if url in self.redump_db.entries_by_url:
                entry = self.redump_db.entries_by_url[url]
                hashkey = self.redump_db.entries_by_url[url].site_hash
                if hashkey in self.mr.media_hashes:
                    dat_entry_name = self.mr.media_hashes[hashkey].dat_game_entry.name
                    print(f"✅ Matched existing media: {part.part_of.name} to {dat_entry_name}")
                    if part.game_entry is not None:
                        print('    [Info] replacing existing source references for this part')
                    part.game_entry = self.mr.media_hashes[hashkey].dat_game_entry
                    part.cdmedia = self.mr.media_hashes[hashkey]
            else:
                print(f'{part.redump_url} no longer in redump, removing reference')
                part.redump_url = ''
                match_failures.append(part)
        return match_failures

    def validate_matched_entries(self) -> None:
        """
        Validate zip files for all matched entries in MediaRegistry
        """
        if not self.mr:
            print("MediaRegistry not initialized")
            return

        zip_processor = ZipProcessor()

        for media in self.mr.media_directory:
            print(f"Validating media ID {media.id} for {media.dat_game_entry.name if media.dat_game_entry else 'Unknown Game'}")
            if not hasattr(media, 'dat_game_entry') or media.dat_game_entry is None or media.softlist_part is None:
                print("  ⚠️ Skipping - No valid DAT game entry or softlist part reference")
                continue

            # Find ROM directory for this DAT
            rom_dir = media.dat_game_entry.dat.rom_path
            if not os.path.isdir(rom_dir):
                print(f"  ⚠️ Skipping - ROM directory does not exist: {rom_dir}")
                continue

            # Find and validate zip
            zip_path = zip_processor.find_valid_zip(media.dat_game_entry, rom_dir)
            if not zip_path:
                print(f"  ⚠️ No valid zip found for {media.dat_game_entry.name} in {rom_dir}")
                continue
            else:
                print(f"  ✅ Found valid zip for {media.dat_game_entry.name}: {zip_path}")
                media.zip_path = zip_path
                self.matched_buildable_media.append(media)

    def build_chds_for_matched(self) -> None:
        """
        Convert all matched entries in MediaRegistry to CHD format.
        """
        media_to_process = self.matched_buildable_media[self._chd_build_index:]
        for matched in media_to_process:
            title = matched.softlist_part.part_of.name if matched.softlist_part and matched.softlist_part.part_of else "Unknown"
            try:
                # initialize CHD object
                print(f"Converting {matched.zip_path} to CHD")
                print(f"  Media ID {matched.id} for {matched.dat_game_entry.name if matched.dat_game_entry else 'Unknown Game'}")
                print(f"  softlist title: {title}")
                matched_chd = CHD(source=matched, base_path=self.chd_path)

                if matched_chd.preexisting:
                    print(f"⚠️  CHD already exists for {matched.dat_game_entry.name} at {matched_chd.path}")

                    if self.chd_handling_preference == "skip":
                        print("   Skipping as per user preference")
                        self.validated_chds.append(matched_chd)
                        continue
                    elif self.chd_handling_preference == "ask":
                        user_input = input("   Overwrite existing CHD? (y/n): ").strip().lower()
                        if user_input != 'y':
                            print("   Skipping conversion")
                            self.validated_chds.append(matched_chd)
                            continue
                    # If overwrite, proceed to create new CHD
                    elif self.chd_handling_preference == "overwrite":
                        print("   Overwriting existing CHD as per user preference")

                if matched_chd.exists and matched_chd.is_valid:
                    self.validated_chds.append(matched_chd)
                    print(f"Successfully converted {matched.zip_path} to CHD")

            except Exception as e:
                self._last_chd_error = (str(e))
                raise  # This exits the function, but we know where to resume


class CHDAlreadyExistsException(Exception):
    def __init__(self, chd_path: str, chd_version: Optional[str] = None):
        self.chd_path = chd_path
        self.chd_version = chd_version
        super().__init__(f"CHD already exists at {chd_path}")



class PlayStationPlatform(Platform):
    def handle_chd_special_cases(self, source_rom_path: str, chd_path: str) -> bool:
        from .psx.libcrypt import libcrypt_titles
        # PlayStation-specific CHD handling logic here
        pass
