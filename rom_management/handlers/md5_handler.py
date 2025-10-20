from .base import SpecialHandler
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor
from rom_management.archive.zip_processor import MD5ScanRequiredException
from menus.progress import ValidationProgressMenu
from rom_management.exceptions import UserActionRequiredException

class MD5ScanHandler(SpecialHandler):
    def __init__(self):
        super().__init__("md5_scan_handler")
        self.menu = ValidationProgressMenu()
    
    def _handle(self, exception: Exception, process) -> dict:
        """Handle MD5 scanning requirements"""
        if isinstance(exception, MD5ScanRequiredException):
            # Check user preferences first
            prefs = process.state['user_preferences']
            
            if prefs.get('skip_md5', False):
                # User chose to skip all MD5 scans
                process.state['current_index'] += 1
                return {'success': True, 'continue': True}
            elif prefs.get('use_md5', False):
                # User chose to use MD5 for all scans
                return self._perform_md5_scan(process.current_item)
            else:
                # Need user input - raise the menu
                raise UserActionRequiredException(
                    f"MD5 scan required for {process.current_item.dat_game_entry.name}",
                    menu_class_name="validation_progress_menu"
                )
    
    def handle_user_action(self, action: str, process) -> dict:
        """Handle user actions from the menu"""
        if action == 'skip':
            process.state['current_index'] += 1
            return {'success': True}
        elif action == 'skip_all':
            process.state['user_preferences']['skip_md5'] = True
            process.state['current_index'] += 1
            return {'success': True}
        elif action == 'scan_md5':
            return self._perform_md5_scan(process.current_item)
        elif action == 'scan_all_md5':
            process.state['user_preferences']['use_md5'] = True
            return self._perform_md5_scan(process.current_item)
        elif action == 'stop':
            return {'complete': True, 'stopped_early': True}
        else:
            # Default behavior
            return {'success': False}
    
    def _perform_md5_scan(self, media: CDMedia) -> dict:
        """Actually perform the MD5 scan"""
        # This would be implemented in a real system
        # For now, we'll simulate the behavior
        from rom_management.archive.zip_processor import ZipProcessor
        zip_processor = ZipProcessor()
        
        try:
            zip_path = zip_processor.find_valid_zip(
                media.dat_game_entry,
                media.dat_game_entry.dat.rom_path,
                md5=True
            )
            if zip_path:
                media.zip_path = zip_path
                return {'success': True}
            else:
                return {'success': False}
        except Exception as e:
            # If MD5 scan fails, we still return success to continue processing
            print(f"MD5 scan failed: {e}")
            return {'success': False}
    
    def _requires_user_intervention(self, error: Exception) -> bool:
        """MD5 scan always requires user intervention"""
        return isinstance(error, MD5ScanRequiredException)
