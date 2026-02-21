from .base import SpecialHandler
from media_registry import CDMedia
from rom_management.processing.models import Action, ResultObject
from rom_management.archive.zip_processor import (
    TimeoutError,
    calculate_timeout,
    with_timeout,
)
from typing import TYPE_CHECKING
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
    ) -> "ResultObject":
        """
        Execute MD5 scanning actions

        Args:
            action: The Action enum representing user's choice
            process: The BaseProcess instance
            params: Optional parameters for action

        Returns:
            ResultObject from executing the action
        """
        if action == Action.SCAN_MD5:
            original_use_md5 = process.use_md5
            process.use_md5 = True

            try:
                return self._execute_step_with_timeout(process)
            finally:
                process.use_md5 = original_use_md5

        elif action == Action.SCAN_ALL_MD5:
            process.use_md5 = True
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

    def validate_preconditions(self, media: CDMedia, file_data=None) -> "ResultObject":
        """Check if this handler should be applied.

        Returns:
            - ResultObject.success() if MD5 scanning might be needed (include handler)
            - ResultObject.not_applicable() if no MD5 scanning needed (don't include handler)
        """
        if not media.dat_game_entry or not media.dat_game_entry.dat:
            return ResultObject.not_applicable(message="No DAT entry")

        dat = media.dat_game_entry.dat
        needs_md5_scan = any(
            hasattr(rom, "md5") and rom.md5 and not (hasattr(rom, "crc") and rom.crc)
            for rom in dat.roms
        )

        if needs_md5_scan:
            return ResultObject.success()

        return ResultObject.not_applicable(message="No MD5 scanning needed")
