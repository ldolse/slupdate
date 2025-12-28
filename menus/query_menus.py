from menus.menu_system import BaseMenu, MenuItem
from rom_management.processing.models import PendingInputPayload, Action, ResultObject
from typing import Optional, Tuple, TYPE_CHECKING
import inquirer

if TYPE_CHECKING:
    from menus.menu_system import MenuSystem


class GenericQueryMenu(BaseMenu):
    """Generic menu handler for all user queries during process execution"""

    def __init__(self):
        super().__init__("generic_query_menu")
        self.message = "User input required"

    def display_and_get_input(
        self, payload: PendingInputPayload
    ) -> Tuple[Action, Optional[dict]]:
        """Display query and get user action"""

        # Build options from valid_actions using display_name
        options = [
            {"name": action.display_name, "value": action}
            for action in payload.valid_actions
        ]

        # Display message and item info
        print(f"\n{payload.message}")
        if hasattr(payload.item, "display_name"):
            print(f"Item: {payload.item.display_name}\n")

        # Use inquirer for user selection
        questions = [
            inquirer.List(
                "action", message="What would you like to do?", choices=options
            )
        ]

        answers = inquirer.prompt(questions)
        selected_action = answers["action"]

        return (selected_action, None)

    def execute(self, menu_system: "MenuSystem") -> ResultObject:
        """
        Legacy execute method - bridges old MenuItem system to new flow.
        Called when this menu is displayed via navigate_to().
        """
        # Check if there's a pending process waiting for input
        if hasattr(menu_system, "_pending_action_handler"):
            handler, result = menu_system._pending_action_handler

            # Handler should be this menu
            if handler is self:
                # Display menu and get user action
                action, params = self.display_and_get_input(result.payload)

                # Resume the process with user's action
                menu_system.resume_process(action, params)

                # Return success - control goes back to run_process loop
                return ResultObject.success()

        # Fallback: return to main menu if no pending process
        return ResultObject.complete(destination_menu="main_menu")
