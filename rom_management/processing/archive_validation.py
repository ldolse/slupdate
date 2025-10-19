from typing import Dict, List, Any, TYPE_CHECKING
import os
from .base_process import BaseProcess
from rom_management.archive.zip_processor import ZipProcessor, MD5ScanRequiredException

if TYPE_CHECKING:
    from media_registry import CDMedia

class ArchiveValidationProcess(BaseProcess):
    """Process for validating matched entries"""

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
        print(f"{self.state['total_items'] } to process, excluding {orig_length - self.state['total_items']}")
        self.zip_processor = ZipProcessor()

    def execute_step(self) -> dict:
        if self.state['current_index'] >= self.state['total_items']:
            return {'complete': True}

        # Get current media item
        media: CDMedia = self.state['items_to_process'][self.state['current_index']]

        # check media with softwarelist & dat matches
        if media.matched:
            try:
                # Validate this media item
                result = self._validate_single_media(media)

                if result.get('success'):
                    self.state['processed_count'] += 1
                    # Add to matched_buildable_media since we know it's valid
                    self.platform.matched_buildable_media[media] = None

                # Always increment counter after processing
                self.state['current_index'] += 1
                return {'continue': True}
            except MD5ScanRequiredException as e:
                # Store exception payload and pause processing for user input
                self.state['exception_payload'] = e
                return {'needs_user_input': True, 'payload': e}
            except Exception as e:
                # Store exception payload and pause processing for user input
                self.state['exception_payload'] = e
                return {'needs_user_input': True, 'payload': e}
        else:
            # Skip unmatched media
            self.state['failed_count'] += 1
            self.state['current_index'] += 1
            return {'continue': True}

    def _validate_single_media(self, media) -> dict:
        """Validate a single media item"""
        # Skip if this media signature is already validated
        media_sig = media.sha1_signature or media.crc_signature
        if media_sig in self.platform.state.matched_media_sigs:
            print(f". ✅ {media.dat_game_entry.name} already validated, skipping zip check")
            return {'success': True}

        if not media.dat_game_entry.name:
            print(f"  ⚠️  Media ID: {media.id} - skipping, No DAT Game name")
            return {'success': True}


        # Find ROM directory for this DAT
        rom_dir = media.dat_game_entry.dat.rom_path
        if not os.path.isdir(rom_dir):
            print(f"  ⚠️  ROM directory does not exist for {media.dat_game_entry.name}: Skipping - {rom_dir}")
            return {'success': True}

        # Find and validate zip
        try:
            zip_path = self.zip_processor.find_valid_zip(media.dat_game_entry, rom_dir)
        except MD5ScanRequiredException as e:
            # Re-raise the exception to be caught by execute_step
            raise e

        if not zip_path:
            print(f"  ⚠️  No valid zip found: {media.dat_game_entry.name}")
            return {'success': False, 'payload': Exception(f"No valid zip found for {media.dat_game_entry.name}")}
        else:
            print(f"  ✅ Found valid zip: {media.dat_game_entry.name}")
            media.zip_path = zip_path
            return {'success': True}


    def handle_user_action(self, action: str) -> dict:
        if action == 'retry':
            # Retry current item - don't advance index
            self.user_preference = None  # Reset preference
            return {'continue': True}
        elif action == 'skip':
            # Don't advance index here - will be done in execute_step
            self.state['failed_count'] += 1
            return {'continue': True}
        elif action == 'stop':
            return {'complete': True, 'stopped_early': True}
        elif action == 'skip_all':
            self.user_preference = 'skip_all'
            # Don't advance index here - will be done in execute_step
            self.state['failed_count'] += 1
            return {'continue': True}
        elif action == 'continue_all':
            self.user_preference = 'continue_all'
            return {'continue': True}
        elif action == 'scan_md5':
            # Perform MD5 scan for current item
            media = self.get_current_item()
            if media:
                try:
                    # Try to validate with MD5 scan
                    zip_path = self.zip_processor.find_valid_zip(media.dat_game_entry, media.dat_game_entry.dat.rom_path, md5=True)
                    if zip_path:
                        media.zip_path = zip_path
                        self.state['processed_count'] += 1
                    else:
                        self.state['failed_count'] += 1
                except Exception as e:
                    print(f"MD5 scan failed: {e}")
                    self.state['failed_count'] += 1
            # Don't advance index here - will be done in execute_step
            return {'continue': True}
        elif action == 'scan_all_md5':
            self.user_preference = 'scan_all_md5'
            return {'continue': True}
