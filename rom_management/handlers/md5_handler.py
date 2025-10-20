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
    
    def _handle(self, media: CDMedia, file_data: OpticalMediaProcessor) -> dict:
        """Handle MD5 scanning requirements"""
        # Always raise an exception that requires user intervention
        raise UserActionRequiredException(
            f"MD5 scan required for {media.dat_game_entry.name}",
            menu_class_name="validation_progress_menu"
        )
    
    def _requires_user_intervention(self, error: Exception) -> bool:
        """MD5 scan always requires user intervention"""
        return isinstance(error, MD5ScanRequiredException)
