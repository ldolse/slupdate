from modules.dat import DAT
from modules.platform import Platform, PlayStationPlatform
from modules.utils import select_directory
import os, pickle
from typing import Optional
import inquirer

class PlatformManager:
    def __init__(self):
        self.platforms = {}
        self._current_key: Optional[str] = None  # Tracks currently selected platform
        self.consoles = {'Amiga CDTV' : 'cdtv',
                         'Amiga CD32' : 'cd32',
                        'FM Towns CD' : 'fmtowns_cd',
                   'IBM PC/AT CD-ROM' : 'ibm5170_cdrom',
                'NEC PC-9801 CD-ROMs' : 'pc98_cd',
          'PC Engine / TurboGrafx CD' : 'pcecd',
                       'Philips CD-i' : 'cdi',
                     'Pippin CD-ROMs' : 'pippin',
                          'NEC PC-FX' : 'pcfx',
                            'Sega CD' : 'segacd',
              'Sega Mega CD (Europe)' : 'megacd',
               'Sega Mega CD (Japan)' : 'megacdj',
                        'Sega Saturn' : 'saturn',
                     'Sega Dreamcast' : 'dc',
                      'SNK NeoGeo CD' : 'neocd',
                   'Sony Playstation' : 'psx',
                                '3DO' : '3do_m2'
        }
        self.datroot: Optional[str] = None
        self.romroot: Optional[str] = None
        self.chdroot: Optional[str] = None
        self.mame_hash_dir: Optional[str] = None
        self.romvault: bool = True

    @property
    def current_platform(self) -> Optional["Platform"]:
        """Returns the currently active Platform object."""
        if not self._current_key:
            return None
        return self.get_platform(self._current_key)

    def initialize_settings(self):
        if not self.datroot:
            print("Configure root DAT directory...")
            self.datroot = select_directory('DAT Root')
        if not self.romroot:
            print("Configure root ROM directory...")
            self.romroot = select_directory('ROM Root')
        if not self.mame_hash_dir:
            print("Configure MAME Software List (hash) directory...")
            self.mame_hash_dir = select_directory('MAME Hash', start_dir=self.datroot)
        if not self.chdroot:
            print("CHD Root directory...")
            self.chdroot = select_directory('CHD Folder', start_dir=self.romroot)
        if not hasattr(self, 'romvault'):
            romvault_answer = inquirer.confirm("Are you using RomVault?")
            self.romvault = romvault_answer

    def add_platform_dat_directory(
        self,
        platform_key: str,
        dat_directory_path: str,
    ):
        """
        Process all DAT files under `dat_directory_path`, creating DAT instances and assigning ROM directories.
        - For RomVault: Maps based on directory structure + DAT metadata name
        - For manual mode: User selects a single ROM directory for each DAT
        """
        platform = self.get_platform(platform_key)
        
        if not os.path.exists(dat_directory_path) or not os.path.isdir(dat_directory_path):
            print(f"Directory `{dat_directory_path}` does not exist.")
            return

        dat_files = [f for f in sorted(os.listdir(dat_directory_path)) 
                    if f.endswith(".xml") or f.endswith(".dat")]
        
        # RomVault: Generate base ROM directory from DAT dir
        rom_dir_base = dat_directory_path.replace(self.datroot, self.romroot, 1)
        
        dats_in_dir = []
        
        for file_name in sorted(dat_files):
            full_path = os.path.join(dat_directory_path, file_name)
            
            # Skip DAT files that can't be parsed (e.g., non-XML .dat files)
            try:
                dat = DAT(full_path)
            except Exception as e:
                print(f"Skipping invalid DAT {file_name}: {e}")
                continue
            
            if self.romvault and len(dat_files) > 1:
                # Create subdirectory based on DAT metadata name
                rom_subdir = os.path.join(rom_dir_base, dat.name)
                if not os.path.exists(rom_subdir):
                    print(f"RomVault subdirectory `{rom_subdir}` does not exist.")
                    continue
                dat.rom_directory = rom_subdir
            else:
                # Use the base ROM directory for single DATs or manual mode
                if self.romvault and os.path.exists(rom_dir_base):
                    dat.rom_directory = rom_dir_base
                elif not self.romvault:
                    prompt_msg = f"Select ROM directory for DAT: {file_name}"
                    rom_subdir = select_directory("ROM", start_dir=self.romroot)
                    dat.rom_directory = rom_subdir
            
            dats_in_dir.append(dat)
            self.save()

        # Store in platform's dat_directories as a dict of {dir_path: [DAT instances]}
        if not hasattr(platform, "dat_directories"):
            platform.dat_directories = {}

        platform.dat_directories[dat_directory_path] = dats_in_dir


    def get_platform(self, key: str) -> "Platform":
        """
        Returns the platform object for the given key, creating it if it doesn't exist.
        """
        if key not in self.platforms:
            name_from_consoles = next(
                (name for name, platform_key in self.consoles.items() if platform_key == key),
                key
            )
            softlist_xml_path = os.path.join(self.mame_hash_dir, f"{key}.xml")
            chd_path = os.path.join(self.chdroot, key)
            # Create the appropriate subclass based on platform key
            if key == 'psx':
                platform = PlayStationPlatform(key=key, name=name_from_consoles, softlist_xml_path=softlist_xml_path, chd_path=chd_path)
            else:
                platform = Platform(key=key, name=name_from_consoles, softlist_xml_path=softlist_xml_path, chd_path=chd_path)
            self.platforms[key] = platform
        return self.platforms[key]

    def get_configured_platforms(self) -> list[tuple[str, str]]:
        """
        Returns a list of (name, key) tuples for platforms that are initialized and have DAT files.
        """
        configured = []
        for platform_key, platform_obj in self.platforms.items():
            if len(platform_obj.dat_directories) > 0:
                configured.append((platform_obj.name, platform_key))
        return configured

    def select_platform(self, show_all: bool = False) -> Optional["Platform"]:
        """Prompt the user to select a configured or all available platforms.
        
        Returns:
            Platform instance corresponding to the selected key.
        """
        if not self.platforms:
            show_all = True # Show all platforms if no configured platforms are found
        if show_all:
            candidates = [(name, key) for name, key in self.consoles.items()]
        else:
            # Only list platforms with at least one DAT directory
            candidates = self.get_configured_platforms()

        if not candidates:
            print("No configured or available platforms.")
            return None

        answer: str = inquirer.list_input(
            message="Select a platform",
            choices=candidates,
            carousel=True
        )

        # Update internal state
        self._current_key = answer  # Store the key for later use (e.g., menus)
        
        # Return the corresponding Platform instance
        return self.get_platform(answer)

    def save(self):
        """Saves the PlatformManager instance and resets _current_key."""
        try:
            self._current_key = None # Reset current key before saving
            with open("platform_manager.pkl", "wb") as f:
                pickle.dump(self, f)
            print("[INFO] Configuration saved.")
        except Exception as e:
            print(f"[ERROR] Could not save configuration: {e}")