from .base import SpecialHandler
from media_registry import CDMedia
from rom_management.processing.models import Action, ResultObject
from rom_management.archive.zip_processor import (
    TimeoutError,
    calculate_timeout,
    with_timeout,
)
from typing import TYPE_CHECKING, Optional, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from rom_management.processing.base_process import BaseProcess


class MD5ScanHandler(SpecialHandler):
    """
    Handles MD5 scan requirements during archive validation.
    Provides options to scan current item, scan all, skip, or stop.
    """

    SKIP_CATEGORY = "MD5 scanning"

    def __init__(self):
        super().__init__("md5_scan_handler")

    def execute_action(
        self,
        action: "Action",
        process: "BaseProcess",
        params: Optional[Dict[str, Any]] = None,
    ) -> "ResultObject":
        """
        Execute an action for this handler.

        This is used by interactive handlers that respond to user actions
        (e.g., MD5ScanHandler, CHDExistenceHandler).

        Args:
            action: The Action enum representing user's choice
            process: The BaseProcess instance
            params: Optional parameters for the action

        Returns:
            ResultObject with SUCCESS or ERROR status
        """
        if action == Action.SCAN_MD5:
            # Store MD5 requirement in handler state on current item
            current_item = process.current_item
            if hasattr(current_item, "_handler_state"):
                current_item._handler_state["require_md5"] = True
            else:
                # Fallback for tests or items without handler state
                logger.warning(f"current_item does not have _handler_state attribute")

            return self._execute_step_with_timeout(process)

        elif action == Action.SCAN_ALL_MD5:
            # Store MD5 requirement in handler state on current item
            current_item = process.current_item
            if hasattr(current_item, "_handler_state"):
                current_item._handler_state["require_md5"] = True
            else:
                # Fallback for tests or items without handler state
                logger.warning(f"current_item does not have _handler_state attribute")

            return self._execute_step_with_timeout(process)

        elif action == Action.SKIP:
            return process._handle_skip("Skipped MD5 scan for current item")

        elif action == Action.SKIP_ALL:
            return process._handle_skip_all(
                f"Skip all {self.SKIP_CATEGORY}", category=self.SKIP_CATEGORY
            )

        elif action == Action.STOP:
            return process._handle_stop()

        return ResultObject.error(
            error_type="UnknownAction",
            message=f"Unknown action for MD5ScanHandler: {action.value}",
        )

    def execute(
        self, media: "CDMedia", file_data: Any = None, process: Any = None
    ) -> "ResultObject":
        """Execute MD5 handler - returns pending_input to prompt user for action.

        This is called during automated processing when validate_preconditions
        returned success (MD5 scanning might be needed).

        Args:
            media: The CDMedia object being processed
            file_data: Optional file data from extraction
            process: The BaseProcess instance (to access current_item)
        """
        from rom_management.processing.models import Action, ResultObject

        # Get the Part from media for display
        part = getattr(media, "softlist_part", None)
        if not part:
            part = getattr(media, "part", None)

        from rom_management.processing.models import PartProcessingItem

        item = PartProcessingItem(part) if part else None

        # Return pending_input to prompt user
        return ResultObject.pending_input(
            query_id="generic_query",
            message=f"MD5 scan required for {media.dat_game_entry.name}",
            item=item,
            valid_actions=[
                Action.SCAN_MD5,
                Action.SCAN_ALL_MD5,
                Action.SKIP,
                Action.SKIP_ALL,
                Action.STOP,
            ],
        )

    def _execute_step_with_timeout(self, process: "BaseProcess") -> "ResultObject":
        """Execute step with size-based timeout for MD5 scanning"""
        zip_path = None
        media_name = "unknown"

        if process.current_item and hasattr(process.current_item, "part"):
            media = process.current_item.part.cdmedia
            zip_path = getattr(media, "zip_path", None)
            media_name = (
                getattr(media.dat_game_entry, "name", "unknown")
                if media and hasattr(media, "dat_game_entry")
                else "unknown"
            )

        if zip_path and os.path.exists(zip_path):
            timeout = calculate_timeout(zip_path)
            logger.debug(f"MD5 scan timeout for {timeout}s: {zip_path}")
        else:
            timeout = 300
            logger.debug(f"Using default timeout {timeout}s (no ZIP path)")

        @with_timeout(timeout)
        def do_md5_scan():
            return self._execute_step_and_advance(process)

        try:
            return do_md5_scan()
        except TimeoutError:
            logger.warning(f"MD5 scan timeout, skipping: {media_name}")
            return process._handle_skip("MD5 scan timed out")

    def validate_preconditions(
        self, media: CDMedia, file_data: Any = None
    ) -> "ResultObject":
        """Check if this handler should be applied.

        Returns:
            - ResultObject.success() if MD5 scanning might be needed (include handler)
            - ResultObject.not_applicable() if no MD5 scanning needed (don't include handler)
        """
        from rom_management.processing.models import ResultObject

        if not media.dat_game_entry:
            return ResultObject.not_applicable(message="No DAT entry")

        dat_entry = media.dat_game_entry
        logger.debug(f"MD5 validate: checking {dat_entry.name}")

        try:
            roms = dat_entry.roms
        except (AttributeError, TypeError) as e:
            logger.debug(f"MD5 validate: Exception accessing roms: {e}")
            return ResultObject.not_applicable(message="No ROMs available")

        try:
            for rom in roms:
                has_md5 = hasattr(rom, "md5") and rom.md5
                has_crc = hasattr(rom, "crc") and rom.crc
                logger.debug(
                    f"MD5 validate: ROM {getattr(rom, 'name', 'unknown')}: md5={bool(has_md5)}, crc={bool(has_crc)}"
                )

            needs_md5_scan = any(
                hasattr(rom, "md5")
                and rom.md5
                and not (hasattr(rom, "crc") and rom.crc)
                for rom in roms
            )
        except (TypeError, AttributeError) as e:
            logger.debug(f"MD5 validate: Exception in logic: {e}")
            return ResultObject.not_applicable(message="Cannot iterate ROMs")

        if needs_md5_scan:
            logger.debug(f"MD5 validate: MD5 scanning IS needed")
            return ResultObject.success()

        logger.debug(f"MD5 validate: No MD5 scanning needed")
        return ResultObject.not_applicable(message="No MD5 scanning needed")
