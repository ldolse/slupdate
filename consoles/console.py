#from modules.dat import DAT
import os
from dat import RomDat
from modules.software_list import shift_sibling_comments, convert_xml, build_sl_dict
from softwarelist import SoftwareList, Part
from utils.utils import select_directory
from media_registry import MediaRegistry
from game_metadata import RedumpDB

from typing import TYPE_CHECKING
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

    @property
    def _all_dats(self) -> list[RomDat]:
        """Flatten all DAT instances across directories."""
        return [dat for dats_list in self.dat_directories.values() for dat in dats_list]

    
    @property
    def dat_rom_dict(self):
        dat_rom_dict = {}
        for dat_instance in self._all_dats:
            dat_path = dat_instance.path
            dat_rom_dict[dat_path] = dat_instance.rom_directory
        return dat_rom_dict

    @property
    def total_parts(self):
        return sum(len(e.parts) for e in self.softwarelist.software_items)


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
        This orchestrates the complete data processing pipeline.
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
                    elif not self.romvault:
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
                if hashkey in self.mr.media_directory:
                    dat_entry_name = self.mr.media_directory[hashkey].dat_game_entry.name
                    print(f"✅ Matched existing media: {part.part_of.name} to {dat_entry_name}")
                    if part.game_entry is not None:
                        print('    [Info] replacing existing source references for this part')
                    part.game_entry = self.mr.media_directory[hashkey].dat_game_entry
                    part.cdmedia = self.mr.media_directory[hashkey]
            else:
                print(f'{part.redump_url} no longer in redump, removing reference')
                part.redump_url = ''
                match_failures.append(part)
        return match_failures



class PlayStationPlatform(Platform):
    def handle_chd_special_cases(self, source_rom_path: str, chd_path: str) -> bool:
        from .psx.libcrypt import libcrypt_titles
        # PlayStation-specific CHD handling logic here
        pass
