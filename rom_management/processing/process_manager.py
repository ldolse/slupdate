from typing import Dict, Optional, TYPE_CHECKING
from .base_process import BaseProcess
from .archive_validation import ArchiveValidationProcess
from .chd_build_process import ChdBuildProcess

if TYPE_CHECKING:
    from consoles import Platform
    from menus.menu_system import MenuSystem

class ProcessManager:
    """Manages long-running processes with user interaction"""

    # Navigation constants
    VALIDATION_MENU = "validation_progress_menu"
    CHD_BUILD_MENU = "chd_build_progress_menu"
    HANDLER_ERROR_MENU = "handler_error_menu"
    EXISTING_CHD_MENU = "existing_chd_menu"

    def __init__(self, platform: 'Platform'):
        self.platform = platform
        self.current_process: Optional[BaseProcess] = None
        self.menu_system: Optional["MenuSystem"] = None

    def set_menu_system(self, menu_system: "MenuSystem"):
        """Set the menu system for navigation"""
        self.menu_system = menu_system

    def start_validation(self) -> dict:
        """Start the CHD validation process"""
        self.current_process = ArchiveValidationProcess(self.platform)
        self.current_process.initialize()

        # Process steps until completion or error
        while True:
            result = self.current_process.execute_step()

            if result.get('complete'):
                # Process finished
                self.current_process = None
                return {'menu': 'main_menu', 'payload': result}
            elif result.get('needs_user_input'):
                # Return menu for user input
                return {'menu': self.VALIDATION_MENU, 'payload': self.current_process}

    def start_chd_build(self) -> dict:
        """Start the CHD building process"""
        self.current_process = ChdBuildProcess(self.platform)
        self.current_process.initialize()

        # Process steps until completion or error
        while True:
            result = self.current_process.execute_step()

            if result.get('complete'):
                # Process finished
                self.current_process = None
                return {'menu': 'main_menu', 'payload': result}
            elif result.get('needs_user_input'):
                # Return menu for user input
                return {'menu': self.EXISTING_CHD_MENU, 'payload': self.current_process}

    def continue_processing(self, action: str) -> dict:
        """Continue the current process with user action"""
        if not self.current_process:
            return {'menu': 'main_menu', 'payload': None}

        # Handle the user action first
        result = self.current_process.handle_user_action(action)

        # Check if process is complete after handling action
        if result.get('complete'):
            self.current_process = None
            return {'menu': 'main_menu', 'payload': result}

        # Execute next step if not complete
        while True:
            next_result = self.current_process.execute_step()

            if next_result.get('complete'):
                # Process finished
                self.current_process = None
                return {'menu': 'main_menu', 'payload': next_result}
            elif next_result.get('needs_user_input'):
                # Return menu for user input
                return {'menu': self._get_progress_menu_name(), 'payload': self.current_process}

    def _get_progress_menu_name(self) -> str:
        """Get the appropriate progress menu name based on current process"""
        if isinstance(self.current_process, ArchiveValidationProcess):
            return self.VALIDATION_MENU
        elif isinstance(self.current_process, ChdBuildProcess):
            return self.CHD_BUILD_MENU
        else:
            return 'main_menu'
