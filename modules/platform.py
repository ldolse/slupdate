from modules.dat import DAT
from modules.software_list import shift_sibling_comments, convert_xml, build_sl_dict
from modules.utils import *
from typing import Dict, List

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
        self.softlist_xml_path = softlist_xml_path
        self.chd_path = chd_path
        self.software_list_data = {}  # MAME software list data
        self.dat_directories: Dict[str, List[DAT]] = {}
        self.redump_data = {}           # Redump site data
        self.dat_hashes = {}         # Hashes for DAT files
        self._stats_cache = {}

    @property
    def _all_dats(self) -> List[DAT]:
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
        if 'total_parts' not in self._stats_cache:
            parts = sum(len(e['parts']) for e in self.software_list_data.values())
            self._stats_cache['total_parts'] = parts
        return self._stats_cache['total_parts']

    def build_dat_hashes(self) -> None:
        """Process all DAT files for this platform, building hash/name lookup tables."""
        # Initialize top-level keys if they don't exist
        for key in ['dat_group', 'name_lookup', 'hashes', 'duplicates']:
            self.dat_hashes.setdefault(key, {})

        print(f'Processing {self.name} DAT Files')
        for dat_instance in self._all_dats:
            try:
                # Build hash/name data from the DAT file
                keyresult, nameresult = dat_instance.build_hash_dict()
                
                # Extract DAT group and path
                dat_path = dat_instance.path
                
                # Update top-level dictionaries in self.dat_hashes
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
        raw_slist = convert_xml(self.softlist_xml_path,process_comments)
        softdict = dict(raw_slist['softwarelist'])

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


class PlayStationPlatform(Platform):
    def handle_chd_special_cases(self, source_rom_path: str, chd_path: str) -> bool:
        from modules.libcrypt import process_libcrypt
        # PlayStation-specific CHD handling logic here
        return process_libcrypt(source_rom_path, chd_path)

