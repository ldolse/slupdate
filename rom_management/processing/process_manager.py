from typing import Dict, Optional, TYPE_CHECKING
from .base_process import BaseProcess
from .archive_validation import ArchiveValidationProcess
from .chd_build_process import ChdBuildProcess
from rom_management.handlers.registry import HandlerRegistry
from rom_management.archive.zip_processor import MD5ScanRequiredException

if TYPE_CHECKING:
    from consoles import Platform
    from menus.menu_system import MenuSystem
    from media_registry import CDMedia
    from rom_management.handlers import SpecialHandler

class ProcessManager:
    """Manages long-running processes with user interaction"""

    def __init__(self, platform: 'Platform'):
        self.platform = platform
        self.current_process: Optional[BaseProcess] = None
        self.menu_system: Optional["MenuSystem"] = None
        self.handler_registry = HandlerRegistry()

    def set_menu_system(self, menu_system: "MenuSystem"):
        """Set the menu system for navigation"""
        self.menu_system = menu_system

    def initialize_handlers(self):
        """Initialize the handler registry with default handlers"""
        from rom_management.handlers.md5_handler import MD5ScanHandler
        self.handler_registry.register_special_handler('md5_scan', MD5ScanHandler)

    def get_handler_for_exception(self, exception: Exception, media: 'CDMedia') -> Optional['SpecialHandler']:
        """Find a handler that can handle this exception"""
        # Get all special handlers
        special_handlers = self.handler_registry.get_special_handlers()
        
        for handler in special_handlers:
            try:
                if handler.validate_preconditions(media, None):
                    # Check if this handler can handle the exception type
                    if isinstance(exception, MD5ScanRequiredException):
                        return handler
            except:
                continue
        
        return None

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
                # Get the appropriate menu from the handler system
                exception = self.current_process.state['exception_payload']
                
                # Find a handler for this exception
                handler = self.get_handler_for_exception(exception, self.current_process.current_item)
                
                if handler:
                    return {'menu': handler.get_menu_name(), 'payload': self.current_process}
                else:
                    # No specific handler found, use default validation menu
                    return {'menu': 'validation_progress_menu', 'payload': self.current_process}

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
                # Get the appropriate menu from the handler system
                exception = self.current_process.state['exception_payload']
                
                # Get handlers that can handle this exception
                handlers = self.handler_registry.get_relevant_handlers(
                    self.current_process.current_item,
                    None  # No file_data for this case
                )
                
                # Find handler that can handle this exception
                for handler in handlers:
                    try:
                        if handler.validate_preconditions(self.current_process.current_item, None):
                            return {'menu': handler.get_menu_name(), 'payload': self.current_process}
                    except:
                        continue
                
                # No specific handler found, use default CHD menu
                return {'menu': 'existing_chd_menu', 'payload': self.current_process}

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
                # Get the appropriate menu from the handler system
                exception = self.current_process.state['exception_payload']
                
                # Find a handler for this exception
                handler = self.get_handler_for_exception(exception, self.current_process.current_item)
                
                if handler:
                    return {'menu': handler.get_menu_name(), 'payload': self.current_process}
                else:
                    # No specific handler found, determine default menu based on process type
                    if isinstance(self.current_process, ArchiveValidationProcess):
                        return {'menu': 'validation_progress_menu', 'payload': self.current_process}
                    elif isinstance(self.current_process, ChdBuildProcess):
                        return {'menu': 'existing_chd_menu', 'payload': self.current_process}
                    else:
                        return {'menu': 'main_menu', 'payload': None}
