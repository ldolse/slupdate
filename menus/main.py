from menus.menu_system import BaseMenu, MenuItem
from menus.menu_system.adapters import DeclarativeMenuAdapter
from rom_management.processing.models import ResultObject


class MainMenu(DeclarativeMenuAdapter, BaseMenu):
    def __init__(self):
        super().__init__("main_menu")
        self.message = "Main Menu"

        # Create menu items without the action function
        self.options = [
            MenuItem(
                text="a. Mapping Functions", target="map_menu", requires_platform=False
            ),
            MenuItem(
                text="b. Create CHDs from ROMs",
                target="chd_build_menu",
                requires_platform=True,
            ),
            MenuItem(
                text="c. Settings", target="settings_menu", requires_platform=False
            ),
            MenuItem(
                text="d. Save Settings",
                action_func=self._save_settings,
                requires_platform=False,
            ),
            MenuItem(text="e. Exit", target="Exit", requires_platform=False),
        ]

    def _save_settings(self, platform_manager):
        """Method that will be called with the platform manager when selected"""
        platform_manager.save()
        return ResultObject.complete(total_processed=1)
