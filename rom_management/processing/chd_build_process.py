import logging
import os
from typing import TYPE_CHECKING
from .base_process import BaseProcess
from .models import (
    ResultObject,
    Action,
    MediaProcessingItem,
)
from optical_media.utils import OpticalMediaProcessor
from rom_management import CHD

if TYPE_CHECKING:
    from consoles import Platform

logger = logging.getLogger(__name__)


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
            logger.warning(
                f"Skipping - No valid softlist part or title for media ID {media.id}"
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

        # Get handlers BEFORE any work (CHD existence check happens here)
        handlers, skip_result = self.platform.get_relevant_handlers(media, None, self)

        # Use centralized handler skip handling (advances item properly)
        skip_handled = self._handle_handler_skip_result(skip_result)
        if skip_handled:
            return skip_handled

        # Run handlers (CHDExistenceHandler may return pending_input, success, or skip)
        handler_result = self._run_handlers(handlers, media, None)
        if handler_result.requires_input():
            return handler_result

        # If handler returned skip (TRUST), item was advanced
        if self.current_item is None:
            return ResultObject.success(message="CHD trusted")

        # Handler returned success (OVERWRITE or no existing CHD) - continue to build
        return self._build_single_chd(media, soft_title, expected_chd_path)

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
                return ResultObject.pending_input(
                    query_id="generic_query",
                    message=f"Temp directory creation for {media.dat_game_entry.name} failed",
                    item=self.current_item,
                    valid_actions=[
                        Action.SKIP,
                        Action.SKIP_ALL,
                        Action.CONTINUE,
                        Action.STOP,
                    ],
                )

            # Prepare for CHD conversion
            toc_source = self._file_data.current_toc

            if not toc_source:
                return ResultObject.pending_input(
                    query_id="generic_query",
                    message=f"No TOC file found for {media.dat_game_entry.name}",
                    item=self.current_item,
                    valid_actions=[
                        Action.SKIP,
                        Action.SKIP_ALL,
                        Action.CONTINUE,
                        Action.STOP,
                    ],
                )

            # Create CHD
            print(f"  Creating CHD at: {expected_chd_path}")
            matched_chd = CHD(
                source=media,
                base_path=self.platform.chd_path,
                toc_source=str(toc_source),
            )

            logger.debug(
                f"CHD object created, exists={matched_chd.exists}, is_valid={matched_chd.is_valid}"
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
                return ResultObject.pending_input(
                    query_id="generic_query",
                    message=f"CHD creation failed for {media.dat_game_entry.name}",
                    item=self.current_item,
                    valid_actions=[
                        Action.SKIP,
                        Action.SKIP_ALL,
                        Action.CONTINUE,
                        Action.STOP,
                    ],
                )

        except OSError as e:
            if e.errno == 28:
                return ResultObject.pending_input(
                    query_id="generic_query",
                    message=f"Insufficient disk space to build CHD for {media.dat_game_entry.name}. Please free up space and try again.",
                    item=self.current_item,
                    valid_actions=[
                        Action.SKIP,
                        Action.SKIP_ALL,
                        Action.STOP,
                    ],
                )
            else:
                return ResultObject.pending_input(
                    query_id="generic_query",
                    message=f"OS error processing {media.dat_game_entry.name}: {str(e)}",
                    item=self.current_item,
                    valid_actions=[
                        Action.SKIP,
                        Action.SKIP_ALL,
                        Action.CONTINUE,
                        Action.STOP,
                    ],
                )
        except Exception as e:
            logger.exception(f"Unexpected error processing {media.dat_game_entry.name}")
            return ResultObject.pending_input(
                query_id="generic_query",
                message=f"Unexpected error processing {media.dat_game_entry.name}: {str(e)}",
                item=self.current_item,
                valid_actions=[
                    Action.SKIP,
                    Action.SKIP_ALL,
                    Action.CONTINUE,
                    Action.STOP,
                ],
            )
        finally:
            # Clean up temp directory
            if hasattr(self, "_file_data") and self._file_data:
                try:
                    self._file_data.cleanup()
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")
