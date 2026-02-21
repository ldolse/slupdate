from abc import ABC
from typing import Optional, Dict, Any, TYPE_CHECKING
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor

if TYPE_CHECKING:
    from rom_management.processing.models import Action, ResultObject
    from rom_management.processing.base_process import BaseProcess


class SpecialHandler(ABC):
    def __init__(self, name: str, menu=None):
        self.name = name
        self.menu = menu  # Associated menu for user interaction

    def validate_preconditions(
        self, media: CDMedia, file_data: OpticalMediaProcessor
    ) -> "ResultObject":
        """Check if this handler should be applied.

        Returns:
            - ResultObject.success(): Include handler
            - ResultObject.not_applicable(): Don't include handler (not relevant for this media)
            - ResultObject.skip(): Skip this item entirely (handler relevant but can't process)
        """
        return ResultObject.success()

    def _execute_step_and_advance(self, process: "BaseProcess") -> "ResultObject":
        """
        Helper method for handlers that need to execute a step and advance to next item.

        This wraps _execute_step() with the advancement logic, so handlers don't need
        to manually advance items on success.

        Args:
            process: The BaseProcess instance

        Returns:
            ResultObject from executing the step
        """
        result = process._execute_step()
        if result.is_success():
            process.processed_items += 1
            process.current_item = None
        return result

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
        raise NotImplementedError(
            f"Handler {self.name} must implement execute_action() "
            "if it handles interactive actions"
        )

    def execute(
        self, media: CDMedia, file_data: OpticalMediaProcessor
    ) -> "ResultObject":
        """
        Execute automated handler logic.

        This is used by automated handlers that perform conversions
        without user interaction (e.g., CloneCDHandler, BinCueHandler, MdFHandler).

        Args:
            media: The CDMedia object being processed
            file_data: The OpticalMediaProcessor with extracted files

        Returns:
            ResultObject with SUCCESS or ERROR status
        """
        raise NotImplementedError(
            f"Handler {self.name} must implement execute() "
            "if it performs automated processing"
        )
