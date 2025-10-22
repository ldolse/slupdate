from typing import Dict, List, Any, TYPE_CHECKING
import os
from .base_process import BaseProcess
from rom_management.archive.zip_processor import ZipProcessor, MD5ScanRequiredException

if TYPE_CHECKING:
    from media_registry import CDMedia
    from consoles import Platform
    from softwarelist import Part

class ArchiveValidationProcess(BaseProcess):
    """Process for validating matched entries"""

    def __init__(self, platform: 'Platform'):
        super().__init__(platform)
        self.zip_processor = ZipProcessor()
        # Process-specific preference
        self.use_md5 = False  # Default to fast validation

    @property
    def progress(self) -> dict:
        """Return current progress information"""
        success_count = 0
        failure_count = 0

        for i, item in enumerate(self.items_to_process):
            if i < self.processed_items:
                # Check if this item was processed successfully
                media = self.items_to_process[i].media
                if media in self.platform.matched_buildable_media:
                    success_count += 1
                else:
                    failure_count += 1

        return {
            'processed': self.processed_items,
            'total': self.total_items,
            'processed': success_count,
            'failed': failure_count,
            'percentage': self._calculate_progress_percentage()
        }

    def initialize(self):
        # Initialize with all media from MediaRegistry
        if not self.platform.mr:
            raise Exception("MediaRegistry not initialized")

        # Get all media items to process
        self.items_to_process = self.platform.all_parts

        self.total_items = len(self.items_to_process)
        print(f"{self.total_items} to process")
        
        # Register handlers
        self.register_handlers()

    def register_handlers(self):
        """Register handlers for this process"""
        from rom_management.handlers.md5_handler import MD5ScanHandler
        self.handlers[MD5ScanRequiredException] = MD5ScanHandler()

    def _execute_step(self) -> dict:
        # Get current media item
        current_part: 'Part' = self.current_item
        media: 'CDMedia' = current_part.cdmedia
        
        try:
            # Validate this media item
            result = self._validate_single_media(media)
            if result.get('success'):
                # Add to matched_buildable_media since we know it's valid
                self.platform.matched_buildable_media[media] = None

            return {'success': True}
        except MD5ScanRequiredException as e:
            # Store exception payload and pause processing for user input
            if self.skip_all:
                print(f"skipping md5 scan for {media.dat_game_entry.name}")
                return {'success': True}
            else:
                self.exception_payload = e
                return {'needs_user_input': True, 'payload': e}
        except Exception as e:
            # Store exception payload and pause processing for user input
            self.exception_payload = e
            return {'needs_user_input': True, 'payload': e}


    def _validate_single_media(self, media: 'CDMedia') -> dict:
        """Validate a single media item"""
        # Skip if this media signature is already validated
        media_sig = media.sha1_signature or media.crc_signature
        if media_sig in self.platform.state.matched_media_sigs:
            print(f". ✅ {media.dat_game_entry.name} already validated, skipping zip check")
            return {'success': True}

        # Find ROM directory for this DAT
        rom_dir = media.dat_game_entry.dat.rom_path
        if not os.path.isdir(rom_dir):
            print(f"  ⚠️  ROM directory does not exist for {media.dat_game_entry.name}: Skipping - {rom_dir}")
            return {'success': False}

        # Find and validate zip using the process's use_md5 setting
        try:
            zip_path = self.zip_processor.find_valid_zip(media.dat_game_entry, rom_dir, md5=self.use_md5)
                
        except MD5ScanRequiredException as e:
            # Re-raise the exception to be caught by execute_step
            raise e

        if not zip_path:
            print(f"  ⚠️  No valid zip found: {media.dat_game_entry.name}")
            return {'success': False}
        else:
            print(f"  ✅ Found valid zip: {media.dat_game_entry.name}")
            media.zip_path = zip_path
            return {'success': True}

    def handle_user_action(self, action: str) -> dict:
        """Handle user actions from menus"""
        # Delegate to handler system for exception-related actions
        if self.exception_payload:
            return super().handle_user_action(action)
        
        # Handle default actions (not tied to exceptions)
        return self._handle_default_user_action(action)
