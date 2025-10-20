from .base import SpecialHandler
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor
from rom_management.archive.zip_processor import MD5ScanRequiredException
from menus.progress import ValidationProgressMenu

class MD5ScanHandler(SpecialHandler):
    def __init__(self):
        super().__init__("md5_scan_handler")
        self.menu = ValidationProgressMenu()
    
    def _handle(self, media: CDMedia, file_data: OpticalMediaProcessor) -> dict:
        """Handle MD5 scanning requirements"""
        # This handler doesn't directly process the media
        # It just raises an exception to trigger user interaction
        raise MD5ScanRequiredException(f"MD5 scan required for {media.dat_game_entry.name}")
    
    def _requires_user_intervention(self, error: Exception) -> bool:
        """MD5 scan always requires user intervention"""
        return isinstance(error, MD5ScanRequiredException)
