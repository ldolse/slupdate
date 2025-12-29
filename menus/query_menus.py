from menus.menu_system import BaseMenu, MenuItem
from menus.menu_system.adapters import DynamicMenuAdapter
from rom_management.processing.models import PendingInputPayload, Action, ResultObject
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from menus.menu_system import MenuSystem


class GenericQueryMenu(DynamicMenuAdapter, BaseMenu):
    """Generic menu handler for all user queries during process execution"""

    def __init__(self):
        super().__init__("generic_query_menu")
        self.message = "User input required"
        self._pending_result = None
        self._pending_handler = None
