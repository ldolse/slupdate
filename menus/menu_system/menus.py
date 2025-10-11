from typing import Dict, Optional
import inspect
from consoles.platform_manager import PlatformManager
from consoles import Platform

# Core Classes for Navigation System
class MenuItem:
    """Represents a single menu option"""
    def __init__(self, text: str,
                 target: Optional[str] = None,
                 action_func = None,
                 requires_platform: bool = True,
                 is_back: bool = False):
        self.text = text  # Displayed text in the menu
        self.target_name = target  # Menu name to navigate to (e.g., "map_menu")
        self.action = action_func  # Callable function (must return a string menu name)
        self.requires_platform = requires_platform
        self.is_back = is_back  # Indicates if this option is a "back" action

    def execute(self, menu_system: "MenuSystem") -> str:
        """Execute option logic and return next target."""
        # Handle back action
        if self.is_back:
            menu_system.navigate_back()
            return None

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
                        print("No platform selected. Action requires a configured platform.")
                        return self.target_name  # Stay on the same menu

                    current_platform = selected_platform
                args.append(current_platform)

            # Explicitly add PlatformManager if required in action signature
            if "platform_manager" in params_needed:
                args.append(menu_system.platform_manager)

            # Add MenuSystem if required in action signature
            if "menu_system" in params_needed:
                args.append(menu_system)

        except Exception as e:
            print(f"Error preparing arguments for {self.text}: {e}")
            return self.target_name  # Default to target

        try:
            result = None
            if self.action:
                result = self.action(*args)

        except TypeError as te:
            print(f"[ERROR] TypeError in action: {te}. Using default.")

        next_target = (
            result
            if isinstance(result, str) and result != ""
            else self.target_name  # Fallback to target name
        )

        return next_target


class BaseMenu:
    """Base class for all menus"""
    def __init__(self, name: str):
        self.name = name
        self.message = f"Message not set - should be defined by subclass {name}"
        self._options = []

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
        self.stack = []  # Navigation history (LIFO)
        self.current_menu_name = None
        self.menus: Dict[str, BaseMenu] = {}  # Registry of all menus by name

        # Platform management
        self.platform_manager = PlatformManager()

    @property
    def current_platform_obj(self) -> Optional["Platform"]:
        return self.platform_manager.current_platform

    def register(self, menu: BaseMenu):
        """Adds a new menu to the system"""
        if not isinstance(menu, BaseMenu):
            raise TypeError("Only instances of BaseMenu can be registered")
        self.menus[menu.name] = menu
        # Inject PlatformManager into menu
        menu.platform_manager = self.platform_manager

    @property
    def current_menu(self) -> BaseMenu:
        return self.menus.get(self.current_menu_name)

    def navigate_to(self, target: str) -> None:
        """Pushes current menu to stack and navigates"""
        # Only add previous state to stack if current menu exists (not initial run)
        if self.current_menu_name:
            if self.current_menu_name != target:
                # Check if target is already in stack to avoid duplicates
                if not any(item['menu_name'] == target for item in self.stack):
                    # Push current menu state to stack
                    self.stack.append({
                        'menu_name': self.current_menu_name,
                    })
        self.current_menu_name = target

    def navigate_back(self) -> Optional[str]:
        """Pops from stack to return to previous menu"""
        if not self.stack:
            return None # Already at root

        last_state = self.stack.pop()
        self.current_menu_name = last_state['menu_name']
        return self.current_menu_name


