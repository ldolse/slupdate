from typing import Dict, List, Any, TYPE_CHECKING
import os
from .base_process import BaseProcess
from rom_management.archive.zip_processor import ZipProcessor, MD5ScanRequiredException

if TYPE_CHECKING:
    from media_registry import CDMedia

class ArchiveValidationProcess(BaseProcess):
    """Process for validating matched entries"""

    @property
    def progress(self) -> dict:
        """Return current progress information"""
        success_count = 0
        failure_count = 0

        for i, item in enumerate(self.state['items_to_process']):
            if i < self.state['current_index']:
                # Check if this item was processed successfully
                media = self.state['items_to_process'][i]
                if media in self.platform.matched_buildable_media:
                    success_count += 1
                else:
                    failure_count += 1

        return {
            'current': self.state['current_index'],
            'total': self.state['total_items'],
            'processed': success_count,
            'failed': failure_count,
            'percentage': self._calculate_progress_percentage()
        }

    def initialize(self):
        self.md5 = False
        # Initialize with all media from MediaRegistry
        if not self.platform.mr:
            raise Exception("MediaRegistry not initialized")

        # Get all media items to process
        self.state['items_to_process'] = list(self.platform.mr.media_directory.keys())
        orig_length = len(self.state['items_to_process'])

        # Filter out already validated items
        self.state['items_to_process'] = [
            media for media in self.state['items_to_process']
            if (media.sha1_signature or media.crc_signature) not in self.platform.state.matched_media_sigs
        ]

        self.state['total_items'] = len(self.state['items_to_process'])
        print(f"{self.state['total_items']} to process, excluding {orig_length - self.state['total_items']}")
        self.zip_processor = ZipProcessor()

    def _execute_step(self) -> dict:
        # Get current media item
        media: 'CDMedia' = self.current_item

        if media.matched:
            try:
                # Validate this media item
                result = self._validate_single_media(media)
                if result.get('success'):
                    # Add to matched_buildable_media since we know it's valid
                    self.platform.matched_buildable_media[media] = None

                return {'success': True}
            except MD5ScanRequiredException as e:
                # Store exception payload and pause processing for user input
                self.state['exception_payload'] = e
                return {'needs_user_input': True, 'menu': self.menu.name if self.menu else 'validation_progress_menu'}
            except Exception as e:
                # Store exception payload and pause processing for user input
                self.state['exception_payload'] = e
                return {'needs_user_input': True, 'menu': self.menu.name if self.menu else 'validation_progress_menu'}
        else:
            # Skip unmatched media
            return {'success': True}

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

        # Find and validate zip
        try:
            # Check user preferences first
            if self.state['user_preferences'].get('use_md5', False):
                zip_path = self.zip_processor.find_valid_zip(media.dat_game_entry, rom_dir, md5=True)
            else:
                zip_path = self.zip_processor.find_valid_zip(media.dat_game_entry, rom_dir, md5=False)
                
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
        if action == 'retry':
            # Retry current item - don't advance index
            self.user_preference = None  # Reset preference
            return {'success': False}
        elif action == 'skip':
            # Skip current item and advance index
            self.state['current_index'] += 1
            return {'success': False}
        elif action == 'stop':
            return {'complete': True, 'stopped_early': True}
        elif action == 'skip_all':
            # Set preference to skip all future MD5 scans
            self.state['user_preferences']['skip_md5'] = True
            self.state['current_index'] += 1
            return {'success': False}
        elif action == 'continue_all':
            # Set preference to scan all items with MD5
            self.state['user_preferences']['use_md5'] = True
            return {'success': False}
        elif action == 'scan_md5':
            # Scan current item with MD5
            media: 'CDMedia' = self.current_item
            if media:
                try:
                    zip_path = self.zip_processor.find_valid_zip(
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
                    print(f"MD5 scan failed: {e}")
                    return {'success': False}
            # Don't advance index here - will be done in execute_step
            return {'success': False}
        elif action == 'scan_all_md5':
            # Set preference to scan all items with MD5
            self.state['user_preferences']['use_md5'] = True
            return {'success': False}
        
        # Default case - don't advance index
        return {'success': False}
