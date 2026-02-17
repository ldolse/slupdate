import os
from typing import TYPE_CHECKING
from .base_process import BaseProcess
from .models import (
    ResultObject,
    Action,
    MediaProcessingItem,
)
from optical_media.utils import OpticalMediaProcessor
from rom_management import CHD, CHDAlreadyExistsException

if TYPE_CHECKING:
    from consoles import Platform


class ChdBuildProcess(BaseProcess):
    """Process for building CHDs from validated entries"""

    def __init__(self, platform: "Platform"):
        super().__init__(platform)
        self._chd_handler = None
        self._file_data = None  # Track current OpticalMediaProcessor

    def initialize(self):
        """Initialize the CHD build process with buildable media from platform"""
        # Get media items to process from platform
        media_items = list(self.platform.matched_buildable_media.keys())

        if not media_items:
            print("No buildable media found in platform")
            self.items_to_process = []
            self.total_items = 0
            return

        # Convert media items to MediaProcessingItem objects
        self.set_items_to_process([MediaProcessingItem(media) for media in media_items])

        print(f"{self.total_items} media items to build CHDs for")

        # Register handlers
        self.register_handlers()

    def register_handlers(self):
        """Register handlers for CHD build process"""
        from rom_management.handlers.chd_existence_handler import CHDExistenceHandler

        self._chd_handler = CHDExistenceHandler()

    def _get_handler_for_action(self, action: Action):
        """Map CHD-related actions to CHDExistenceHandler"""
        chd_actions = [
            Action.OVERWRITE,
            Action.TRUST_EXISTING,
            Action.SET_OVERWRITE_PREFERENCE,
            Action.SET_TRUST_PREFERENCE,
            Action.SKIP,
            Action.SKIP_ALL,
            Action.STOP,
        ]
        if action in chd_actions:
            return self._chd_handler
        return None

    def _execute_step(self) -> ResultObject:
        """Execute one step of CHD building"""
        if self.current_item is None:
            if not self._get_next_item():
                return ResultObject.complete(total_processed=self.processed_items)

        media = self.current_item.media

        if not media.softlist_part or not media.softlist_part.part_of:
            print(
                f"  ⚠️  Skipping - No valid softlist part or title for media ID {media.id}"
            )
            return ResultObject.success(
                message=f"Skipped {media.id}: Missing softlist reference",
                metadata={"media_id": media.id},
            )

        soft_title = media.softlist_part.part_of.name
        file_name = media.dat_game_entry.name

        expected_chd_path = os.path.join(
            self.platform.chd_path, soft_title, f"{file_name}.chd"
        )

        if os.path.exists(expected_chd_path):
            return self._handle_existing_chd(media, expected_chd_path)

        return self._build_single_chd(media, soft_title, expected_chd_path)

    def _handle_existing_chd(self, media, expected_chd_path: str) -> ResultObject:
        """Handle case where CHD already exists - check if validated, ask user, or respect preference"""
        matched_chd = CHD(chd_path=expected_chd_path)
        is_valid = matched_chd.exists and matched_chd.is_valid
        is_in_validated_set = any(
            matched_chd.path == chd.path for chd in self.platform.validated_chds
        )

        if is_valid and is_in_validated_set:
            print(f"✅ CHD already validated for {media.dat_game_entry.name}")
            return ResultObject.success(
                message=f"CHD already validated: {media.dat_game_entry.name}",
                metadata={"chd_path": expected_chd_path},
            )

        print(f"⚠️  CHD already exists for {media.dat_game_entry.name}")

        existing_version = None
        if is_valid:
            chd_info = matched_chd._get_chd_info()
            existing_version = chd_info.get("file_version")

        pref = self.platform.chd_handling_preference

        if pref == "skip":
            print(f"Skipping existing CHD per platform preference")
            return ResultObject.success(
                message=f"Skipped existing CHD: {media.dat_game_entry.name}",
                metadata={"chd_path": expected_chd_path, "reason": "preference"},
            )
        elif pref == "overwrite":
            print(f"Overwriting existing CHD per platform preference")
            try:
                os.remove(expected_chd_path)
            except OSError as e:
                return ResultObject.error(
                    error_type="FileRemovalError",
                    message=f"Failed to remove CHD: {str(e)}",
                    exception=e,
                )
            return self._build_single_chd(
                media, media.softlist_part.part_of.name, expected_chd_path
            )
        else:
            return ResultObject.pending_input(
                query_id="generic_query",
                message=f"CHD already exists for {media.dat_game_entry.name}",
                item=self.current_item,
                valid_actions=[
                    Action.OVERWRITE,
                    Action.TRUST_EXISTING,
                    Action.SET_OVERWRITE_PREFERENCE,
                    Action.SET_TRUST_PREFERENCE,
                    Action.SKIP,
                    Action.SKIP_ALL,
                    Action.STOP,
                ],
                options_context={
                    "existing_version": existing_version,
                    "chd_path": expected_chd_path,
                },
            )

    def _build_single_chd(
        self, media, title: str, expected_chd_path: str
    ) -> ResultObject:
        """Build CHD for a single media item"""

        # Check if we have a valid zip_path before attempting extraction
        if not media.zip_path:
            return ResultObject.pending_input(
                query_id="generic_query",
                message=f"Cannot build CHD for {media.dat_game_entry.name}: ZIP path not set. "
                f"Please run 'Validate source ROMs' first.",
                item=self.current_item,
                valid_actions=[
                    Action.SKIP,
                    Action.SKIP_ALL,
                    Action.CONTINUE,
                    Action.STOP,
                ],
            )

        # Initialize OpticalMediaProcessor
        self._file_data = OpticalMediaProcessor(media, tmpdsk=self.platform.pm.tmpdsk)

        try:
            print(f"Converting {media.zip_path} to CHD")
            print(f"  softlist title: {title}")

            # Extract the ROM to a temp directory
            self._file_data.extract_and_process()

            if not self._file_data.temp_dir or not self._file_data.temp_dir.exists():
                return ResultObject.error(
                    error_type="TempDirectoryError",
                    message=f"Temp directory creation for {media.dat_game_entry.name} failed",
                    context={"media_id": media.id},
                )

            # Get and apply handlers (only handlers that pass validate_preconditions)
            handlers = self.platform.get_relevant_handlers(media, self._file_data)

            for handler in handlers:
                result = handler.execute(media, self._file_data)

                if not result.is_success():
                    return ResultObject.error(
                        error_type="HandlerFailed",
                        message=f"Handler {handler.name} failed",
                        context={
                            "handler": handler.name,
                            "error": result.payload.message if result.payload else None,
                        },
                    )

            # Prepare for CHD conversion
            toc_source = self._file_data.current_toc

            if not toc_source:
                return ResultObject.error(
                    error_type="NoTOCError",
                    message=f"No TOC file found for {media.dat_game_entry.name}",
                    context={"media_id": media.id},
                )

            # Create CHD
            print(f"  Creating CHD at: {expected_chd_path}")
            matched_chd = CHD(
                source=media,
                base_path=self.platform.chd_path,
                toc_source=str(toc_source),
            )

            print(
                f"  CHD object created, checking exists={matched_chd.exists}, is_valid={matched_chd.is_valid}"
            )

            if matched_chd.exists and matched_chd.is_valid:
                self.platform.validated_chds.add(matched_chd)
                self.platform.state.add_validated_chd_path(str(matched_chd.path))
                print(f"✅ Converted {media.zip_path} to CHD")
                return ResultObject.success(
                    message=f"Created CHD: {media.dat_game_entry.name}",
                    metadata={"chd_path": matched_chd.path},
                )
            else:
                return ResultObject.error(
                    error_type="CHDCreationError",
                    message=f"CHD creation failed for {media.dat_game_entry.name}",
                    context={"media_id": media.id},
                )

        except OSError as e:
            # Catch specific errors like no space left on device (errno 28)
            if e.errno == 28:  # ENOSPC - No space left on device
                return ResultObject.error(
                    error_type="DiskSpaceError",
                    message=f"Insufficient disk space to build CHD for {media.dat_game_entry.name}. Please free up space and try again.",
                    exception=e,
                    context={"media_id": media.id},
                )
            else:
                return ResultObject.error(
                    error_type="OSError",
                    message=f"OS error processing {media.dat_game_entry.name}: {str(e)}",
                    exception=e,
                    context={"media_id": media.id},
                )
        except Exception as e:
            return ResultObject.error(
                error_type="BuildError",
                message=f"Unexpected error processing {media.dat_game_entry.name}: {str(e)}",
                exception=e,
                context={"media_id": media.id},
            )
        finally:
            # Clean up temp directory
            if hasattr(self, "_file_data") and self._file_data:
                try:
                    self._file_data.cleanup()
                except Exception as e:
                    print(f"Warning: Failed to cleanup temp directory: {e}")
