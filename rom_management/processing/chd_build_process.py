from typing import Dict, Any
import os
from .base_process import BaseProcess
from optical_media.utils import OpticalMediaProcessor
from rom_management import CHD
from rom_management.exceptions import HandlerException, UserActionRequiredException, SkipCurrentItemException

class ChdBuildProcess(BaseProcess):
    """Process for building CHDs from validated entries"""

    def initialize(self):
        """Initialize the CHD build process"""
        # Get media items to process from platform
        self.state['items_to_process'] = list(self.platform.matched_buildable_media.keys())
        self.state['total_items'] = len(self.state['items_to_process'])

    def execute_step(self) -> dict:
        """Execute one step of CHD building"""
        if self.state['current_index'] >= self.state['total_items']:
            return {'complete': True}

        # Get current media item
        media = self.state['items_to_process'][self.state['current_index']]

        try:
            # Execute CHD building for this media
            result = self._build_single_chd(media)

            if result.get('success'):
                self.state['processed_count'] += 1
            else:
                # Store exception payload and pause processing
                self.state['exception_payload'] = result.get('payload')
                return {'needs_user_input': True, 'payload': result['payload']}

        except HandlerException as e:
            # Store exception payload and pause processing
            self.state['exception_payload'] = e
            return {'needs_user_input': True, 'payload': e}
        except Exception as e:
            # Store exception payload and pause processing
            self.state['exception_payload'] = e
            return {'needs_user_input': True, 'payload': e}

        self.state['current_index'] += 1
        return {'continue': True}

    def _build_single_chd(self, media) -> dict:
        """Build CHD for a single media item"""
        # Implementation from Platform.build_chds_for_matched()
        # Check if CHD already exists and is validated
        title = media.softlist_part.part_of.name if media.softlist_part and media.softlist_part.part_of else None
        if not title:
            return {'success': False, 'payload': Exception(f"No valid softlist part or title for media ID {media.id}")}

        # Check if this CHD is already validated
        expected_chd_path = os.path.join(self.platform.chd_path, title, f"{media.softlist_part.disk_name}.chd")
        if expected_chd_path in self.platform.state.validated_chds_paths and os.path.exists(expected_chd_path):
            existing_chd = CHD(chd_path=expected_chd_path)
            if existing_chd.is_valid:
                print(f"✅ CHD already validated for {media.dat_game_entry.name}, skipping")
                self.platform.validated_chds.add(existing_chd)
                return {'success': True}
            else:
                # will try to rebuild if it's not reported as valid
                os.remove(expected_chd_path)

        elif os.path.exists(expected_chd_path):
            matched_chd = CHD(chd_path=expected_chd_path)
            print(f"⚠️  CHD already exists for {media.dat_game_entry.name} at {expected_chd_path}")

            # Create exception with existing version info
            from rom_management.exceptions import CHDAlreadyExistsException
            existing_version = matched_chd._get_chd_info().get('file_version') if matched_chd.is_valid else None
            exception = CHDAlreadyExistsException(expected_chd_path, existing_version)

            return {'success': False, 'payload': exception}

        file_data = OpticalMediaProcessor(media, tmpdsk=self.platform.pm.tmpdsk)

        try:
            # initialize CHD object
            print(f"Converting {media.zip_path} to CHD")
            print(f"  softlist title: {title}")

            # Extract the ROM to a temp directory
            file_data.extract_and_process()

            if not file_data.temp_dir.exists():
                return {'success': False, 'payload': Exception(f"Temp directory creation for {media.dat_game_entry.name} failed")}

            # Get and apply handlers
            handlers = self.platform.get_relevant_handlers(media, file_data)

            for handler in handlers:
                try:
                    result = handler.handle(media, file_data)
                    if not result.get('success', True):
                        return {'success': False, 'payload': HandlerException(f"Handler {handler.name} failed: {result.get('error')}")}
                except SkipCurrentItemException:
                    print(f"Skipping item due to handler request")
                    return {'success': False, 'payload': Exception("Handler requested skip")}
                except UserActionRequiredException as e:
                    return {'success': False, 'payload': e}

            # Prepare for CHD conversion
            toc_source = file_data.current_toc

            matched_chd = CHD(source=media, base_path=self.platform.chd_path, toc_source=toc_source)

            if matched_chd.exists and matched_chd.is_valid:
                self.platform.validated_chds.add(matched_chd)
                self.platform.state.add_validated_chd_path(matched_chd.path)
                print(f"✅ Converted {media.zip_path} to CHD")
                return {'success': True}

        except Exception as e:
            print(f"Unexpected error processing {media.dat_game_entry.name}: {e}")
            return {'success': False, 'payload': e}
        finally:
            # Clean up temp directory
            if file_data:
                file_data.cleanup()

        return {'success': False, 'payload': Exception("Unknown error in CHD building")}

    def handle_user_action(self, action: str) -> dict:
        """Handle user actions after exceptions"""
        if action == 'retry':
            # Retry current item
            return {'continue': True}
        elif action == 'skip':
            self.state['failed_count'] += 1
            self.state['current_index'] += 1
            return {'continue': True}
        elif action == 'stop':
            return {'complete': True, 'stopped_early': True}
        elif action == 'overwrite':
            # Set preference and retry
            self.platform.set_chd_preference("overwrite")
            return {'continue': True}
        elif action == 'skip_existing':
            # Set preference and continue
            self.platform.set_chd_preference("skip")
            return {'continue': True}