from typing import Dict, List, Any, TYPE_CHECKING
from .base_process import BaseProcess
from rom_management.archive.zip_processor import ZipProcessor, MD5ScanRequiredException

class ArchiveValidationProcess(BaseProcess):
    """Process for validating matched entries"""

    def initialize(self):
        # Initialize with all media from MediaRegistry
        if not self.platform.mr:
            raise Exception("MediaRegistry not initialized")

        # Get all media items to process
        self.state['items_to_process'] = list(self.platform.mr.media_directory.keys())

        # Filter out already validated items
        self.state['items_to_process'] = [
            media for media in self.state['items_to_process']
            if (media.sha1_signature or media.crc_signature) not in self.platform.state.matched_media_sigs
        ]

        self.state['total_items'] = len(self.state['items_to_process'])
        self.zip_processor = ZipProcessor()

    def execute_step(self) -> dict:
        if self.state['current_index'] >= self.state['total_items']:
            return {'complete': True}

        # Get current media item
        media = self.state['items_to_process'][self.state['current_index']]

        try:
            # Validate this media item
            result = self._validate_single_media(media)

            if result.get('success'):
                self.state['processed_count'] += 1
                # Add to matched_buildable_media since we know it's valid
                self.platform.matched_buildable_media[media] = None

                # Only increment index if successful
                self.state['current_index'] += 1
                return {'continue': True}
            else:
                # Check if we have a "skip all" preference
                if self.user_preference == 'skip_all':
                    self.state['failed_count'] += 1
                    self.state['current_index'] += 1
                    return {'continue': True}
                # Store exception payload and pause processing for user input
                self.state['exception_payload'] = result.get('payload')
                return {'needs_user_input': True, 'payload': result['payload']}

        except MD5ScanRequiredException as e:
            # Store exception payload and pause processing for user input
            self.state['exception_payload'] = e
            return {'needs_user_input': True, 'payload': e}
        except Exception as e:
            # Store exception payload and pause processing for user input
            self.state['exception_payload'] = e
            return {'needs_user_input': True, 'payload': e}

    def _validate_single_media(self, media) -> dict:
        """Validate a single media item"""
        # Skip if this media signature is already validated
        media_sig = media.sha1_signature or media.crc_signature
        if media_sig in self.platform.state.matched_media_sigs:
            print(f". ✅ {media.dat_game_entry.name} already validated, skipping zip check")
            return {'success': True}

        if not media.dat_game_entry.name:
            print(f"  ⚠️  Media ID: {media.id} - skipping, No DAT Game name")

        if media.dat_game_entry is None or media.softlist_part is None:
            print(f"  ⚠️  {media.dat_game_entry.name}: Skipping - No valid DAT game entry or softlist part reference")

        # Find ROM directory for this DAT
        rom_dir = media.dat_game_entry.dat.rom_path
        if not os.path.isdir(rom_dir):
            print(f"  ⚠️  {media.dat_game_entry.name}: Skipping - ROM directory does not exist: {rom_dir}")

        # Find and validate zip
        try:
            zip_path = self.zip_processor.find_valid_zip(media.dat_game_entry, rom_dir)
        except MD5ScanRequiredException as e:
            # Re-raise the exception to be caught by execute_step
            raise e
            
        if not zip_path:
            print(f"  ⚠️  {media.dat_game_entry.name}: No valid zip found")
            return {'success': False, 'payload': Exception(f"No valid zip found for {media.dat_game_entry.name}")}
        else:
            print(f"  ✅ {media.dat_game_entry.name}: Found valid zip")
            media.zip_path = zip_path
            return {'success': True}

    def handle_user_action(self, action: str) -> dict:
        if action == 'retry':
            # Retry current item - don't advance index
            self.user_preference = None  # Reset preference
            return {'continue': True}
        elif action == 'skip':
            self.state['failed_count'] += 1
            # Advance index when skipping
            self.state['current_index'] += 1
            return {'continue': True}
        elif action == 'stop':
            return {'complete': True, 'stopped_early': True}
        elif action == 'skip_all':
            self.user_preference = 'skip_all'
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
            # Advance index after processing
            self.state['current_index'] += 1
            return {'continue': True}
        elif action == 'scan_all_md5':
            self.user_preference = 'scan_all_md5'
            return {'continue': True}
