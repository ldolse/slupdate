from .base import SpecialHandler
from media_registry import CDMedia
from rom_management.archive.zip_processor import MD5ScanRequiredException
from menus.progress import ValidationProgressMenu
from rom_management.processing import BaseProcess
from rom_management.exceptions import UserActionRequiredException

class MD5ScanHandler(SpecialHandler):
    def __init__(self):
        super().__init__("md5_scan_handler")
        self.menu = ValidationProgressMenu()

    def _handle(self, exception: Exception, process: 'BaseProcess') -> dict:
        """Handle MD5 scanning requirements"""
        pass

    def handle_user_action(self, action: str, process: 'BaseProcess') -> dict:
        """Handle user actions from the menu"""
        if action == 'skip':
            process.current_item = None
            return {'success': True}
        elif action == 'skip_all':
            process.current_item = None
            process.skip_all = True
            return {'success': True}
        elif action == 'scan_md5':
            # Temporarily enable MD5 for this item
            original_use_md5 = process.use_md5
            process.use_md5 = True

            try:
                # Execute step with MD5 enabled
                return process._execute_step()
            finally:
                # Restore original setting
                process.use_md5 = original_use_md5

        elif action == 'scan_all_md5':
            process.use_md5 = True
            return process._execute_step()
        elif action == 'stop':
            return {'complete': True, 'stopped_early': True}
        else:
            # Default behavior
            return {'success': False}

    def _requires_user_intervention(self, error: Exception) -> bool:
        """MD5 scan always requires user intervention"""
        return isinstance(error, MD5ScanRequiredException)
