from .base import SpecialHandler
from media_registry import CDMedia
from rom_management.archive.zip_processor import MD5ScanRequiredException
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from rom_management.processing.models import Action, ResultObject
    from rom_management.processing.base_process import BaseProcess


class MD5ScanHandler(SpecialHandler):
    """
    Handles MD5 scan requirements during archive validation.
    Provides options to scan current item, scan all, skip, or stop.
    """

    def __init__(self):
        super().__init__("md5_scan_handler")

    def execute_action(
        self,
        action: "Action",
        process: "BaseProcess",
        params: Optional[Dict[str, Any]] = None,
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
        from rom_management.processing.models import (
            ResultObject,
            ProcessStatus,
            Action,
        )

        if action == Action.SCAN_MD5:
            # Temporarily enable MD5 for this item
            original_use_md5 = process.use_md5
            process.use_md5 = True

            try:
                # Execute step with MD5 enabled
                return self._execute_step_and_advance(process)
            finally:
                # Restore original settings
                process.use_md5 = original_use_md5

        elif action == Action.SCAN_ALL_MD5:
            # Set the preference to use MD5 for all items
            process.use_md5 = True

            # Execute step with MD5 enabled
            return self._execute_step_and_advance(process)

        elif action == Action.SKIP:
            # Skip current item
            process.current_item = None
            process.processed_items += 1
            return ResultObject.success(message="Skipped MD5 scan for current item")

        elif action == Action.SKIP_ALL:
            # Skip all remaining MD5-required items
            process.skip_all = True
            process.current_item = None
            process.processed_items += 1
            return ResultObject.success(
                message="Set skip_all preference for remaining items"
            )

        elif action == Action.STOP:
            return ResultObject.complete(
                total_processed=process.processed_items,
                stopped_early=True,
            )

        return ResultObject.error(
            error_type="UnknownAction",
            message=f"Unknown action for MD5ScanHandler: {action.value}",
        )

    def validate_preconditions(self, media: CDMedia, file_data=None) -> bool:
        """Check if this handler should be applied"""
        dat = media.dat_game_entry.dat
        return any(hasattr(rom, "md5") and not hasattr(rom, "crc") for rom in dat.roms)
