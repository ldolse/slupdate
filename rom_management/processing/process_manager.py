from typing import Dict, Optional, TYPE_CHECKING, Type
from .base_process import BaseProcess
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

    def start_process(self, process_class: Type[BaseProcess], **kwargs) -> dict:
        """Start any process with the given class"""
        self.current_process = process_class(self.platform, **kwargs)
        self.current_process.initialize()

        # Execute the first step
        return self.execute_current_step()

    def continue_processing(self, action: str) -> dict:
        """Continue the current process with user action"""
        if not self.current_process:
            return {'menu': 'main_menu', 'payload': None}

        # Handle the user action first
        result = self.current_process.handle_user_action(action)

        # Execute next step if not complete
        return self.execute_current_step()

    def execute_current_step(self) -> dict:
        """Execute the current step of the process"""
        if not self.current_process:
            return {'menu': 'main_menu', 'payload': None}

        try:
            result = self.current_process.execute_step()

            if result.get('complete'):
                # Process finished
                self.current_process = None
                return {'menu': 'main_menu', 'payload': result}
            elif result.get('needs_user_input'):
                # Get the appropriate menu from the handler system
                return {
                    'menu': result['menu'],
                    'payload': self.current_process
                }
            else:
                # Continue processing - but only if not in exception handling state
                return result  # Return the direct result instead of recursing
        except RecursionError:
            # Handle recursion error by stopping the process
            self.current_process = None
            return {'menu': 'main_menu', 'payload': {'error': 'Recursion error occurred'}}

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

    def _get_default_menu_name(self) -> str:
        """Determine default menu name based on current process type"""
        if not self.current_process:
            return 'main_menu'
        
        # Check for specific process types
        if hasattr(self.current_process, '__class__'):
            class_name = self.current_process.__class__.__name__
            
            if 'ArchiveValidation' in class_name:
                return 'validation_progress_menu'
            elif 'ChdBuild' in class_name:
                return 'existing_chd_menu'
        
        # Default fallback
        return 'main_menu'
