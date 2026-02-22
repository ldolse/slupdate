from typing import List, TYPE_CHECKING
import os
import logging
from .base_process import BaseProcess
from .models import (
    ResultObject,
    Action,
    ProcessStatus,
    PartProcessingItem,
    ProgressPayload,
)
from rom_management.archive.zip_processor import (
    ZipProcessor,
    TimeoutError,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from media_registry import CDMedia
    from consoles import Platform
    from softwarelist import Part


class ArchiveValidationProcess(BaseProcess):
    """Process for validating matched entries"""

    def __init__(self, platform: "Platform"):
        super().__init__(platform)
        self.zip_processor = ZipProcessor()
        self._md5_handler = None
        self.use_md5 = False

    @property
    def progress(self) -> dict:
        """Return current progress information"""
        success_count = 0
        failure_count = 0

        for i, item in enumerate(self.items_to_process):
            if i < self.processed_items:
                media = self.items_to_process[i].part.cdmedia
                if media in self.platform.matched_buildable_media:
                    success_count += 1
                else:
                    failure_count += 1

        return {
            "processed": self.processed_items,
            "total": self.total_items,
            "succeeded": success_count,
            "failed": failure_count,
            "percentage": self._calculate_progress_percentage(),
        }

    def initialize(self):
        """Initialize with all media from MediaRegistry"""
        if not self.platform.mr:
            raise Exception("MediaRegistry not initialized")

        self.items_to_process = [
            PartProcessingItem(part) for part in self.platform.all_parts
        ]

        self.total_items = len(self.items_to_process)
        logger.info(f"{self.total_items} items to process")

        self.register_handlers()

    def register_handlers(self):
        """Register MD5 scan handler for this process"""
        from rom_management.handlers.md5_handler import MD5ScanHandler

        self._md5_handler = MD5ScanHandler()

    def _get_handler_for_action(self, action: Action):
        """Map MD5-related actions to MD5ScanHandler"""
        md5_actions = [
            Action.SCAN_MD5,
            Action.SKIP,
            Action.SKIP_ALL,
            Action.SCAN_ALL_MD5,
        ]
        if action in md5_actions:
            return self._md5_handler
        return None

    def _execute_step(self) -> ResultObject:
        """Execute one validation step"""
        current_part: "Part" = self.current_item.part
        media: "CDMedia" = current_part.cdmedia

        logger.info(
            f"[{self.processed_items}/{self.total_items}] {media.dat_game_entry.name}"
        )

        media_sig = media.sha1_signature or media.crc_signature
        if self.platform.state.is_validated(media_sig):
            logger.debug(f"Already validated, skipping")
            saved_zip_path = self.platform.state.get_zip_path(media_sig)
            if saved_zip_path:
                media.zip_path = saved_zip_path
                logger.debug(f"Restored ZIP path: {saved_zip_path}")
            elif not media.zip_path:
                logger.warning(
                    f"No ZIP path found in state for {media.dat_game_entry.name}"
                )
            self.platform.matched_buildable_media[media] = None
            return ResultObject.success(
                message=f"Already validated: {media.dat_game_entry.name}",
                metadata={"media_id": media.id, "zip_path": media.zip_path},
            )

        rom_dir = media.dat_game_entry.dat.rom_path
        if not rom_dir or not os.path.isdir(rom_dir):
            logger.warning(f"ROM directory missing: {rom_dir}")
            return ResultObject.success(
                message=f"ROM directory missing: {media.dat_game_entry.name}",
                metadata={"rom_dir": rom_dir},
            )

        handlers, skip_result = self.platform.get_relevant_handlers(media, None)
        logger.debug(f"Handler check: handlers={handlers}, skip_result={skip_result}")

        # Skip handler check if already in handler execution (prevents infinite loop)
        if self._skip_handler_check:
            logger.debug(f"Skipping handler check - handler is executing step")
            handlers = []
            skip_result = None
        else:
            # Also check special handlers (like MD5ScanHandler) - these don't need file_data
            from rom_management.handlers import registry

            special_handlers = registry.get_special_handlers()
            logger.debug(f"Special handlers: {[h.name for h in special_handlers]}")

            for handler in special_handlers:
                result = handler.validate_preconditions(media, None)
                logger.debug(f"Special handler {handler.name}: result={result.status}")
                if result.is_success():
                    handlers.append(handler)
                    logger.debug(f"Added special handler: {handler.name}")
                elif result.is_skip():
                    return result
                elif result.requires_input():
                    return result

        if skip_result:
            logger.debug(
                f"Skip result: is_skip={skip_result.is_skip()}, requires_input={skip_result.requires_input()}"
            )
            if skip_result.is_skip():
                return skip_result
            elif skip_result.requires_input():
                return skip_result

        for handler in handlers:
            logger.debug(f"Running handler: {handler.name}")
            result = handler.execute(media, None)
            logger.debug(f"Handler result: status={result.status}")
            return result

        try:
            zip_path = self.zip_processor.find_valid_zip(
                media.dat_game_entry, rom_dir, md5=self.use_md5
            )
        except TimeoutError:
            logger.warning(
                f"Timeout reading ZIP, skipping: {media.dat_game_entry.name}"
            )
            return self._handle_skip("Skipped due to timeout")
        except Exception as e:
            logger.error(f"Error validating {media.dat_game_entry.name}: {e}")
            return ResultObject.error(
                error_type="ValidationError",
                message=f"Error validating: {str(e)}",
                exception=e,
                context={"media_id": media.id},
            )

        if not zip_path:
            logger.warning(f"No valid ZIP found: {media.dat_game_entry.name}")
            return ResultObject.success(
                message=f"No valid zip found: {media.dat_game_entry.name}",
                metadata={"media_id": media.id},
            )

        logger.info(f"✓ Found valid ZIP: {zip_path}")
        media.zip_path = zip_path
        self.platform.state.add_validated_zip_path(media_sig, zip_path)
        self.platform.matched_buildable_media[media] = None
        return ResultObject.success(
            message=f"Found valid zip: {media.dat_game_entry.name}",
            metadata={"zip_path": zip_path, "media_id": media.id},
        )
