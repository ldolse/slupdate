from menus.menu_system import BaseMenu, MenuItem
from consoles import Platform, PlatformManager
from typing import List, Tuple
from utils.utils import reconfigure_settings, list_menu

class SettingsMenu(BaseMenu):
    def __init__(self):
        super().__init__("settings_menu")
        self.message = "Settings Menu"
        self.options = [
            MenuItem(
                text="a. Configure DAT/ROM Platform Directories",
                target="dat_menu",
                requires_platform = True
            ),
            MenuItem(
                text = "b. Change Platform",
                action_func = self._platform_select,
                requires_platform = False
            ),
            MenuItem(
                text="c. Reconfigure Global Settings",
                action_func=self._handle_reconfigure_settings,
                requires_platform = False
            ),
            MenuItem(
                text="d. Destination folder for CHDs",
                #action_func=chd_dir_function,
                requires_platform = False
            ),
            MenuItem(
                text="e. Reset Current Platform",
                action_func=self._reset_platform,
            ),
            MenuItem(
                text="[Back to Main Menu]",
                is_back=True,
                requires_platform = False
            )
        ]

    @staticmethod
    def _reset_platform(platform: Platform) -> None:
        """Reset the current platform to its default state."""
        platform.reset()
        print(f"Platform {platform.key} has been reset to its default state.")

    @staticmethod
    def _handle_reconfigure_settings(platform_manager: "PlatformManager"):
        """Handler for re-configuring global settings in this menu."""
        settings_list = [
            ('datroot', 'DAT Root Directory', 'directory'),
            ('romroot', 'ROM Root Directory', 'directory'),
            ('mame_hash_dir', 'MAME Software List (hash) Directory', 'directory'),
            ('tmpdsk', 'Tempfile Directory (RAMdisk Recommended)', 'directory'),
            ('romvault', 'Enable RomVault', 'boolean')
        ]
        reconfigure_settings(instance=platform_manager, settings_list=settings_list)

    @staticmethod
    def _platform_select(platform_manager: PlatformManager) -> None:
        """Select a platform from the list of available platforms."""
        selected_platform = platform_manager.select_platform(show_all=True)
        if selected_platform:
            print(f"Selected platform: {selected_platform.name}")
        else:
            print("No platform selected.")

class DatMenu(BaseMenu):
    def __init__(self):
        super().__init__("dat_menu")
        self.message = f"Configure DAT Directories"
        self.options = [
            MenuItem(
                text = "a. Add Directories",
                action_func = self._platform_add_dat_function,
                requires_platform = True
            ),
            MenuItem(
                text = "b. Remove DAT Directory",
                action_func = self._del_datpath_function,
            ),
            MenuItem(
                text = "c. Back",
                is_back=True,
                requires_platform = False
            )
        ]

    @staticmethod
    def _del_datpath_function(platform: Platform) -> None:
        '''
        removes DATs from the platform settings
        '''
        datlist = list(platform.dat_directories.keys())
        datlist.append('back')
        message = 'Select a DAT to remove from the list'
        answer = list_menu('dat', datlist, message)
        if answer['dat'] == 'back':
            return 'settings_menu'
        else:
            platform.dat_directories.pop(answer['dat'])

    @staticmethod
    def _platform_add_dat_function(platform: Platform, platform_manager: PlatformManager):
        """Select and Configure DAT and ROM directories for a platform."""
        platform_manager.add_dat_function()