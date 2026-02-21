"""Adapter implementations for different menu types.

This module provides adapter mixins that implement the BaseMenu interface for
different menu patterns:

1. DeclarativeMenuAdapter: For MenuItem-based declarative menus (MainMenu,
   SettingsMenu, etc.) - converts MenuItem.options to DisplayData

2. DynamicMenuAdapter: For query menus generated from process results -
   converts PendingInputPayload to DisplayData

Both adapters allow MenuSystem to render all menus uniformly without special
case detection.
"""

from menus.menu_system import BaseMenu, MenuItem
from menus.ux_models import DisplayData
from rom_management.processing.models import ResultObject
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from menus.menu_system import MenuSystem


class DeclarativeMenuAdapter:
    """Adapter for MenuItem-based declarative menus.

    This adapter is used by menus that define their options statically using
    MenuItem objects (MainMenu, SettingsMenu, MapMenu, etc.). It converts
    the MenuItem.options list into DisplayData for rendering.

    Usage:
        class MainMenu(BaseMenu, DeclarativeMenuAdapter):
            def __init__(self):
                super().__init__("main_menu")
                self.options = [...]  # MenuItem objects

            # No need to implement get_display_data() or execute_custom_action()
            # The adapter provides the implementation!
    """

    def get_display_data(self) -> DisplayData:
        """Convert MenuItem.options to DisplayData."""
        choices = [(item.text, item) for item in self.options]
        return DisplayData(message=self.message, choices=choices)

    def execute_custom_action(
        self, menu_system: "MenuSystem", action: Any
    ) -> ResultObject:
        """Execute a MenuItem action."""
        if isinstance(action, MenuItem):
            return action.execute(menu_system)
        raise ValueError(
            f"DeclarativeMenuAdapter expects MenuItem action, got {type(action)}"
        )


class DynamicMenuAdapter:
    """Adapter for dynamic query menus.

    This adapter is used by menus that are generated at runtime from process
    results (GenericQueryMenu). These menus don't have static MenuItem options -
    instead, they build their choices from PendingInputPayload.valid_actions.

    The menu is expected to have:
    - _pending_result: A ResultObject with PendingInputPayload

    Usage:
        class GenericQueryMenu(BaseMenu, DynamicMenuAdapter):
            def __init__(self):
                super().__init__("generic_query_menu")
                self._pending_result = None

            # Set _pending_result when menu is displayed
            # Adapter handles converting it to DisplayData
    """

    def get_display_data(self) -> DisplayData:
        """Convert PendingInputPayload to DisplayData."""
        if not hasattr(self, "_pending_result") or not self._pending_result:
            return DisplayData(message="No pending query", choices=[])

        payload = self._pending_result.payload
        choices = []
        for act in payload.valid_actions:
            display_name = self._get_action_display_name(act, payload.skip_category)
            choices.append((display_name, act))

        message = payload.message
        if hasattr(payload.item, "display_name"):
            message += f"\nItem: {payload.item.display_name}"

        return DisplayData(message=message, choices=choices)

    def _get_action_display_name(self, action, skip_category: str = None) -> str:
        """Get display name for an action, with contextual labels for SKIP actions."""
        from rom_management.processing.models import Action

        if skip_category:
            if action == Action.SKIP:
                return f"Skip this {skip_category}"
            elif action == Action.SKIP_ALL:
                return f"Skip all {skip_category}"

        return action.display_name

    def execute_custom_action(
        self, menu_system: "MenuSystem", action: Any
    ) -> ResultObject:
        """Resume process with user's action.

        The action parameter is expected to be an Action enum from the
        PendingInputPayload.valid_actions list.
        """
        menu_system.resume_process(action, None)
        return ResultObject.success()
