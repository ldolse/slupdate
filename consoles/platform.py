#from modules.dat import DAT
import os, pickle
from dat import RomDat
from modules.software_list import shift_sibling_comments, convert_xml, build_sl_dict
from softwarelist import SoftwareList, Part
from utils.utils import save_data, select_directory
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
        self.software_list_data = {}  # MAME software list data
        self.dat_directories: dict[str, list[RomDat]] = {}
        self.redump_data = {}           # Redump site data
        self.redump_db: RedumpDB = None
        self.dat_hashes = {}         # Hashes for DAT files
        self._stats_cache = {}
        self.mr: MediaRegistry = None

    @property
    def _all_dats(self) -> list[RomDat]:
        """Flatten all DAT instances across directories."""
        return [dat for dats_list in self.dat_directories.values() for dat in dats_list]

    @property
    def total_entries(self):
        return len(self.software_list_data) if self.software_list_data else 0

    @property
    def source_found_count(self):
        if 'source_found' not in self._stats_cache:
            count = sum(1 for entry in self.software_list_data.values() 
                       if getattr(entry, 'source_found', False))
            self._stats_cache['source_found'] = count
        return self._stats_cache['source_found']
    
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

    def build_dat_hashes(self) -> None:
        """Process all DAT files for this platform, building hash/name lookup tables."""
        # Initialize top-level keys if they don't exist
        for key in ['dat_group', 'name_lookup', 'hashes', 'duplicates']:
            self.dat_hashes.setdefault(key, {})

        print(f'Processing {self.name} DAT Files')
        for dat_instance in self._all_dats:
            try:
                # Build hash/name data from the DAT file
                print(f'Building Hash Dict {dat_instance.path}')
                keyresult, nameresult = dat_instance.build_hash_dict()
                
                dat_path = dat_instance.path
                
                # Update top-level dictionaries in self.dat_hashes
                print('group')
                self.dat_hashes['dat_group'][dat_path] = dat_instance.dat_group
                self.dat_hashes['hashes'][dat_path] = keyresult
                self.dat_hashes['name_lookup'][dat_path] = nameresult

            except Exception as e:
                print(f"Error processing DAT {dat_instance.path}: {e}")
        self.remove_duplicate_entries()

    def build_softlist_dict(self) -> None:
        '''
        Processes the software list XML file and builds a dictionary of software entries.
        '''
        
        # process the software list into a dict, creating hash based fingerprints from comments
        print('processing '+self.name+' software list')
        process_comments = True
        shift_sibling_comments(self.softlist_xml_path)
        softdict = convert_xml(self.softlist_xml_path,process_comments)

        # build the dict object with relevant softlist data for this script, return bool whether crc source keys are needed
        build_sl_dict(softdict['software'], self.software_list_data,self.key)

    def update_softlist(self) -> None:
        '''
        updates the software list xml file with new data
        '''
        from modules.software_list import update_rom_source_refs, rewrite_comment_source_group
        # update re-mapped sources from DAT
        update_rom_source_refs(self.softlist_xml_path,self.software_list_data)
        # update the source group reference for unknown/undocumented sources that have been matched
        rewrite_comment_source_group(self.softlist_xml_path,self.software_list_data)

    def remove_duplicate_entries(self) -> None:
        """
        Removes duplicate DAT entries across groups, prioritizing 'redump' hashes.
        Updates self.dat_hashes in-place.
        """
        dupe_count = 0

        for lookup_dat_path, lookup_hash_dict in self.dat_hashes["hashes"].items():
            dat_group = self.dat_hashes["dat_group"][lookup_dat_path]
            
            # Skip redump DATs (we keep them as primary)
            if dat_group == "redump":
                continue
                
            pop_list = []
            
            for source_id in lookup_hash_dict:
                for target_dat_path, target_hash_dict in self.dat_hashes["hashes"].items():
                    target_group = self.dat_hashes["dat_group"][target_dat_path]
                    
                    # Skip same group and redump entries
                    if dat_group == target_group:
                        continue
                        
                    if source_id in target_hash_dict:
                        pop_list.append(source_id)
            
            for to_delete in set(pop_list):  # Use set to avoid duplicates
                if to_delete in lookup_hash_dict:
                    lookup_hash_dict.pop(to_delete)
                    dupe_count += 1

        print(f"Removed {dupe_count} duplicate DAT entries")
    def reset(self):
        """
        Resets the platform's state, clearing software list data and hashes.
        """
        self.software_list_data.clear()
        self.dat_hashes.clear()
        self.redump_data.clear()
        self._stats_cache.clear()

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

