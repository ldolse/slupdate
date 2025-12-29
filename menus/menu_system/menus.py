from typing import Dict, Optional, Tuple, Type, TYPE_CHECKING, Any
import inspect
from abc import ABC, abstractmethod
from consoles.platform_manager import PlatformManager
from consoles import Platform
from rom_management.processing.models import PendingInputPayload, Action, ResultObject
from menus.ux_models import DisplayData

if TYPE_CHECKING:
    from rom_management.processing.models import NavigationPayload, BaseProcess
    from rom_management.processing.process_runner import ProcessRunner


# Core Classes for Navigation System
class MenuItem:
    """Represents a single menu option"""

    def __init__(
        self,
        text: str,
        target: Optional[str] = None,
        action_func=None,
        requires_platform: bool = True,
        is_back: bool = False,
    ):
        self.text = text  # Displayed text in the menu
        self.target_name = target  # Menu name to navigate to (e.g., "map_menu")
        self.action = action_func  # Callable function (must return a string menu name)
        self.requires_platform = requires_platform
        self.is_back = is_back  # Indicates if this option is a "back" action

    def execute(self, menu_system: "MenuSystem") -> "ResultObject":
        """Execute option logic and return ResultObject"""

        # Handle back action
        if self.is_back:
            from rom_management.processing.models import ResultObject

            target = menu_system.navigate_back()
            return ResultObject.complete(total_processed=1, destination_menu=target)

        current_platform = menu_system.current_platform_obj
        try:
            sig = inspect.signature(self.action) if self.action else None
            params_needed = list(sig.parameters.keys()) if self.action and sig else []

            args = []

            # Check platform requirement
            if "platform" in params_needed or self.requires_platform:
                if not current_platform:
                    selected_platform = menu_system.platform_manager.select_platform()
                    if not selected_platform:
                        print(
                            "No platform selected. Action requires a configured platform."
                        )
                        from rom_management.processing.models import ResultObject

                        return ResultObject.complete(
                            total_processed=0, destination_menu=self.target_name
                        )

                    current_platform = selected_platform
                args.append(current_platform)

            # Explicitly add PlatformManager if required in action signature
            if "platform_manager" in params_needed:
                args.append(menu_system.platform_manager)

            # Add MenuSystem if required
            if "menu_system" in params_needed:
                args.append(menu_system)

        except Exception as e:
            print(f"Error preparing arguments for {self.text}: {e}")
            from rom_management.processing.models import ResultObject

            return ResultObject.complete(
                total_processed=0, destination_menu=self.target_name
            )

        try:
            from rom_management.processing.models import ResultObject

            result = None
            if self.action:
                result = self.action(*args)

            # Handle different result types
            if isinstance(result, ResultObject):
                return result
            elif result is None:
                # No action function (e.g., Exit, or navigation-only items)
                # Navigate to target menu
                return ResultObject.complete(
                    total_processed=0, destination_menu=self.target_name
                )
            else:
                # Unexpected return type - should not happen
                print(
                    f"[WARNING] Action function returned unexpected type: {type(result)}"
                )
                return ResultObject.complete(
                    total_processed=0, destination_menu=self.target_name
                )

        except TypeError as te:
            print(f"[ERROR] TypeError in action: {te}. Using default.")
            from rom_management.processing.models import ResultObject

            return ResultObject.complete(
                total_processed=0, destination_menu=self.target_name
            )


class BaseMenu(ABC):
    """Base class for all menus

    All menus must implement:
    - get_display_data(): Returns DisplayData for rendering
    - execute_custom_action(): Handles user action from menu

    This allows MenuSystem to render all menus the same way (currently
    inquirer CLI, future web UI) without knowing menu implementation details.
    """

    def __init__(self, name: str):
        self.name = name
        self.message = f"Message not set - should be defined by subclass {name}"
        self._options = []
        self.payload = None  # Legacy, will be deprecated

    def set_payload(self, payload):
        """Legacy method - for backward compatibility during migration"""
        self.payload = payload

    @abstractmethod
    def get_display_data(self) -> DisplayData:
        """
        Return display data for rendering by MenuSystem.

        This method is called by MenuSystem.render() to get the data needed
        to display the menu to the user. The rendering logic (inquirer CLI,
        React web UI, etc.) is handled by MenuSystem, not the menu.

        Returns:
            DisplayData: Message and choices for rendering
        """
        pass

    @abstractmethod
    def execute_custom_action(
        self, menu_system: "MenuSystem", action: Any
    ) -> ResultObject:
        """
        Execute a user action selected from the menu.

        This method is called after the user makes a selection. The action
        parameter is the value from the selected DisplayData choice.

        Args:
            menu_system: The MenuSystem instance for navigation/orchestration
            action: The action selected by the user (MenuItem, Action enum, etc.)

        Returns:
            ResultObject: Result of executing the action
        """
        pass

    @property
    def options(self) -> list[MenuItem]:
        return self._options

    @options.setter
    def options(self, new_options: list[MenuItem]):
        """Setter ensures all items are MenuItem instances and sets default targets"""
        if not all(isinstance(item, MenuItem) for item in new_options):
            raise TypeError("All menu items must be MenuItem instances")

        # Set default target to the current menu's name if not provided
        for item in new_options:
            if not item.target_name:
                item.target_name = self.name  # Default back to own menu

        self._options = new_options


class MenuSystem:
    """Manages navigation state and history with platform integration"""

    def __init__(self):
        self.stack = []
        self.current_menu_name = None
        self.menus: Dict[str, BaseMenu] = {}

        # Platform management
        self.platform_manager = PlatformManager()

        # Process management
        self._query_handlers: Dict[str, BaseMenu] = {}
        self.runner: Optional["ProcessRunner"] = None
        self._pending_action_handler: Optional[Tuple[BaseMenu, "ResultObject"]] = None

    @property
    def current_menu(self) -> BaseMenu:
        return self.menus.get(self.current_menu_name)

    def register(self, menu: BaseMenu):
        """Adds a new menu to the system"""
        if not isinstance(menu, BaseMenu):
            raise TypeError("Only instances of BaseMenu can be registered")
        self.menus[menu.name] = menu

    def register_query_handler(self, query_id: str, menu: BaseMenu):
        """Register a menu handler for a query_id"""
        self._query_handlers[query_id] = menu

    @property
    def current_platform_obj(self) -> Optional["Platform"]:
        """Convenience property to access current platform"""
        return self.platform_manager.current_platform

    def _get_or_create_query_handler(self, query_id: str) -> BaseMenu:
        """Get existing handler or create generic one lazily"""
        if query_id in self._query_handlers:
            return self._query_handlers[query_id]

        # Lazy load generic handler
        from menus.query_menus import GenericQueryMenu

        handler = GenericQueryMenu()
        self._query_handlers[query_id] = handler
        # Also register in main menus dict so it can be found by current_menu property
        self.menus[handler.name] = handler
        return handler

    @property
    def current_menu(self) -> BaseMenu:
        return self.menus.get(self.current_menu_name)

    def render(self, menu: BaseMenu) -> Any:
        """
        Display menu and return selected action/value.

        This method centralizes all rendering logic for menus. It calls
        get_display_data() on the menu to get the data needed to render,
        then uses inquirer CLI to display it.

        In the future, this could be replaced with web UI API endpoints
        that return DisplayData as JSON.

        Args:
            menu: The menu to render

        Returns:
            The value from the selected choice (MenuItem, Action, etc.)
        """
        display_data = menu.get_display_data()

        print(f"\n{display_data.message}")

        import inquirer

        questions = [
            inquirer.List(
                "action",
                message=display_data.question_text,
                choices=display_data.choices,
            )
        ]

        answers = inquirer.prompt(questions)
        return answers["action"]

    def execute_menu_action(self, menu: BaseMenu, action: Any) -> ResultObject:
        """
        Execute a menu action and handle navigation.

        This method is called after user makes a selection. It delegates
        execution to the menu's execute_custom_action() method, then
        handles navigation based on the ResultObject.

        Args:
            menu: The menu that generated the action
            action: The action selected by the user

        Returns:
            ResultObject: Result of executing the action
        """
        result = menu.execute_custom_action(self, action)

        if result.is_complete() or result.is_error():
            self.navigate_to(result)

        return result

    def navigate_to(self, navigation_info) -> None:
        """Handle ResultObject navigation"""
        if isinstance(navigation_info, ResultObject):
            self._handle_result_navigation(navigation_info)
        # No else branch - all navigation uses ResultObject

    def _handle_result_navigation(self, result: "ResultObject") -> None:
        """Process-aware navigation logic"""
        if result.is_complete():
            # Navigate to destination menu specified in payload
            target = result.payload.destination_menu
            self._navigate_to_menu(target, result.payload)

        elif result.requires_input():
            # Navigate to query handler menu
            handler = self._get_or_create_query_handler(result.payload.query_id)

            # Store the result for the handler to use when rendering
            handler._pending_result = result

            # Navigate to the handler menu
            self._navigate_to_menu(handler.name, result.payload)

        elif result.is_success():
            # SUCCESS means continue with current state - no navigation needed
            pass

        elif result.is_error():
            # Navigate to error destination or main menu
            target = result.payload.destination_menu or "main_menu"
            self._navigate_to_menu(target, result.payload)

    def _navigate_to_menu(self, target: str, payload: Optional[dict] = None) -> None:
        """Navigate to a menu with optional payload injection"""
        if target is None:
            return

        # Inject payload if menu supports it
        if (
            payload
            and target in self.menus
            and hasattr(self.menus[target], "set_payload")
        ):
            self.menus[target].set_payload(payload)

        # Manage navigation stack
        if self.current_menu_name:
            if self.current_menu_name != target:
                if not any(item["menu_name"] == target for item in self.stack):
                    self.stack.append({"menu_name": self.current_menu_name})

        self.current_menu_name = target

    def navigate_back(self) -> Optional[str]:
        """Pops from stack to return to previous menu"""
        if not self.stack:
            return None

        last_state = self.stack.pop()
        self.current_menu_name = last_state["menu_name"]
        return self.current_menu_name

    def run_process(
        self, process_class: Type["BaseProcess"], destination_menu: str = "main_menu"
    ) -> Optional["ResultObject"]:
        """
        Run a process with main loop for user interaction.
        Returns None if process is waiting for user input (PENDING_INPUT).
        Returns ResultObject when process is COMPLETE or ERROR.
        """
        platform = self.current_platform_obj
        if not platform:
            print("No platform selected. Cannot run process.")
            from rom_management.processing.models import ResultObject

            return ResultObject.error(
                error_type="NoPlatform",
                message="No platform selected",
                destination_menu=destination_menu,
            )

        from rom_management.processing.process_runner import ProcessRunner

        self.runner = ProcessRunner(platform)
        self.runner.start_new_process(process_class)

        try:
            while True:
                result = self.runner.execute_next_step()

                if result.is_success() or result.is_progress():
                    # Auto-continue, display message if present
                    if (
                        result.payload
                        and hasattr(result.payload, "message")
                        and result.payload.message
                    ):
                        print(result.payload.message)
                    # Continue loop

                elif result.requires_input():
                    # Navigate to menu via navigate_to()
                    # User interaction will resume loop via resume_process()
                    self.navigate_to(result)
                    # Return None to indicate waiting for user input
                    return None

                elif result.is_complete():
                    # Set default destination if not specified
                    if result.payload and result.payload.destination_menu is None:
                        result.payload.destination_menu = destination_menu
                    return result

                elif result.is_error():
                    # Set default destination if not specified
                    if result.payload and result.payload.destination_menu is None:
                        result.payload.destination_menu = destination_menu
                    return result

        except KeyboardInterrupt:
            # User pressed Ctrl+C
            print("\n\nProcess interrupted by user.")
            # Clean up and return to main menu
            self.runner = None
            from rom_management.processing.models import ResultObject

            return ResultObject.complete(
                total_processed=0, stopped_early=True, destination_menu="main_menu"
            )

    def resume_process(self, action: Action, params: Optional[dict] = None) -> None:
        """
        Resume process after user action from menu.
        Continues the run_process loop from the user's action.
        """
        result = self.runner.handle_user_action(action, params)
        self.run_process_from_result(result)

    def run_process_from_result(self, result: "ResultObject") -> None:
        """Continue process loop from a given ResultObject"""
        while not result.is_complete() and not result.is_error():
            if result.requires_input():
                # Navigate to menu for user input
                self.navigate_to(result)
                return

            if result.is_success() or result.is_progress():
                # Auto-continue on SUCCESS or PROGRESS
                result = self.runner.execute_next_step()
            else:
                break

        # Process finished - handle navigation
        if result.is_complete():
            target = result.payload.destination_menu or "main_menu"
            self._navigate_to_menu(target, result.payload)
        elif result.is_error():
            target = result.payload.destination_menu or "main_menu"
            self._navigate_to_menu(target, result.payload)
