from modules.dat import DAT
from modules.utils import *
from typing import Dict, List

class Platform:
    def __init__(self, key: str, name: str):
        self.key = key  # Unique identifier (e.g., 'psx')
        self.name = name  # User-friendly name (e.g., 'Sony Playstation')
        self.software_list_data = None  # MAME software list data
        self.dat_directories: Dict[str, List[DAT]] = {}
        self.redump_data = {}           # Redump site data
        self._stats_cache = {}
        self.dat_files = []  # List of DAT files associated with this platform

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
    def total_parts(self):
        if 'total_parts' not in self._stats_cache:
            parts = sum(len(e['parts']) for e in self.software_list_data.values())
            self._stats_cache['total_parts'] = parts
        return self._stats_cache['total_parts']


class PlayStationPlatform(Platform):
    def handle_chd_special_cases(self, source_rom_path: str, chd_path: str) -> bool:
        from modules.libcrypt import process_libcrypt
        # PlayStation-specific CHD handling logic here
        return process_libcrypt(source_rom_path, chd_path)

