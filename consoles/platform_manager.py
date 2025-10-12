from consoles.console import Platform
from consoles.platform_state import PlatformState
from utils.utils import select_directory
import os
from typing import Optional
import inquirer
import pickle

class PlatformManager:
    # Define the global variables structure once as a class attribute
    GLOBAL_VAR_KEYS = [
        'romvault',
        'chdroot',
        'mame_hash_dir',
        'romroot',
        'datroot',
        'tmpdsk'
    ]
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
        for key in self.GLOBAL_VAR_KEYS:
            setattr(self, key, None)
        self.last_dat_dir: Optional[str] = None
        self.romvault: bool = True  # Default value

    @property
    def current_platform(self) -> Optional[Platform]:
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
            self.chdroot = select_directory('CHD', start_dir=self.romroot)
        if not self.tmpdsk:
            print("Tempfile Directory (RAMdisk Recommended)...")
            self.tmpdsk = select_directory('Tempfile')
        if not hasattr(self, 'romvault'):
            romvault_answer = inquirer.confirm("Are you using RomVault?")
            self.romvault = romvault_answer

    def add_dat_function(self):
        """Select and Configure DAT and ROM directories for a platform."""
        if not self.current_platform:
            print("No platform selected. Please select a platform first.")
            return
        if self.last_dat_dir:
            dat_directory_path = select_directory("DAT", start_dir=self.last_dat_dir)
            self.last_dat_dir = os.path.dirname(dat_directory_path)
        else:
            dat_directory_path = select_directory("DAT", start_dir=self.datroot)
            self.last_dat_dir = os.path.dirname(dat_directory_path)

        # Process DAT files in directory
        self.add_platform_dat_directory(
            self.current_platform.key,
            dat_directory_path
        )

    def add_platform_dat_directory(
        self,
        platform_key: str,
        dat_directory_path: str,
    ):
        """
        Process all DAT files under `dat_directory_path`, creating DAT instances
        and assigning ROM directories.
        - For RomVault: Maps based on directory structure + DAT metadata name
        - For manual mode: User selects a single ROM directory for each DAT
        """
        platform = self.get_platform(platform_key)

        if not os.path.exists(dat_directory_path) or not os.path.isdir(dat_directory_path):
            print(f"Directory `{dat_directory_path}` does not exist.")
            return

        platform.dat_directories[dat_directory_path] = []


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
            # Create the platform based on the platform key
            platform = Platform(key=key, name=name_from_consoles, softlist_xml_path=softlist_xml_path, chd_path=chd_path)
            platform.pm = self  # Link back to this manager
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
        """Save all platform states using shared PlatformState structure"""
        # Use the class attribute to get global vars
        global_vars = {key: getattr(self, key) for key in self.GLOBAL_VAR_KEYS}

        platforms_data = {}
        for key, platform in self.platforms.items():
            # Save state using PlatformState
            platform_state = platform.save_state()

            # Convert to serializable format
            platforms_data[key] = {
                'dat_directories': platform_state.dat_directories,
                'redump_db': platform_state.redump_db,
                '_chd_build_index': platform_state._chd_build_index,
                'matched_media_sigs': platform_state.matched_media_sigs,
                '_chd_handling_preference': platform_state._chd_handling_preference,
                'validated_chds_paths': platform_state.validated_chds_paths,
                'directory_status': platform_state.directory_status
            }

        data_to_save = {
            'global_vars': global_vars,
            'platforms': platforms_data
        }

        with open('pm.pkl', 'wb') as f:
            pickle.dump(data_to_save, f)
        print("[INFO] Configuration saved.")

    @classmethod
    def load(cls):
        """Load from saved configuration using shared PlatformState structure"""
        try:
            with open('pm.pkl', 'rb') as f:
                loaded_data = pickle.load(f)
        except (FileNotFoundError, EOFError) as e:
            return cls(), False

        pm = cls()
        global_data = loaded_data.get('global_vars', {})
        platform_data = loaded_data.get('platforms', {})

        # Restore global settings using the class attribute
        for key in cls.GLOBAL_VAR_KEYS:
            if key in global_data:
                setattr(pm, key, global_data[key])

        # Rebuild platform-specific data using PlatformState
        for key, info in platform_data.items():
            platform = pm.get_platform(key)

            # Create PlatformState from loaded data
            state = PlatformState(
                dat_directories=info.get('dat_directories', []),
                redump_db=info.get('redump_db'),
                _chd_build_index=info.get('_chd_build_index', 0),
                matched_media_sigs=info.get('matched_media_sigs', []),
                _chd_handling_preference=info.get('_chd_handling_preference'),
                validated_chds_paths=info.get('validated_chds_paths', []),
                directory_status=info.get('directory_status', {})
            )

            # Load state into platform
            platform.load_state(state)

        return pm, True
