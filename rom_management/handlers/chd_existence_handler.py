import os
from typing import Optional, Dict, Any, TYPE_CHECKING

from .base import SpecialHandler

if TYPE_CHECKING:
    from rom_management.processing.models import Action, ResultObject
    from rom_management.processing.base_process import BaseProcess
    from rom_management.exceptions import CHDAlreadyExistsException

else:
    from rom_management.exceptions import CHDAlreadyExistsException


class CHDExistenceHandler(SpecialHandler):
    """
    Handles scenarios where a CHD already exists during CHD build process.
    Provides options to overwrite, skip, or set preferences.
    """

    def __init__(self):
        super().__init__("chd_existence")

    def execute_action(
        self,
        action: "Action",
        process: "BaseProcess",
        params: Optional[Dict[str, Any]] = None,
    ) -> "ResultObject":
        """
        Execute CHD existence actions

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

        if action == Action.OVERWRITE:
            # Remove existing CHD and retry
            exception = self._get_pending_exception(process)
            if exception and isinstance(exception, CHDAlreadyExistsException):
                os.remove(exception.chd_path)
            return process._execute_step()

        elif action == Action.SKIP_EXISTING:
            # Set preference and continue
            process.platform.set_chd_preference("skip")
            process.current_item = None
            process.processed_items += 1
            return ResultObject.success(message="Skipped existing CHD")

        elif action == Action.SET_OVERWRITE_PREFERENCE:
            # Set preference for all remaining items
            process.platform.set_chd_preference("overwrite")
            return process._execute_step()

        elif action == Action.SET_SKIP_PREFERENCE:
            # Set preference for all remaining items
            process.platform.set_chd_preference("skip")
            process.current_item = None
            process.processed_items += 1
            return ResultObject.success(
                message="Set skip preference for remaining CHDs"
            )

        elif action == Action.STOP:
            return ResultObject.complete(
                total_processed=process.processed_items,
                stopped_early=True,
            )

        return ResultObject.error(
            error_type="UnknownAction",
            message=f"Unknown action for CHDExistenceHandler: {action.value}",
        )

    def _get_pending_exception(
        self, process: "BaseProcess"
    ) -> Optional[CHDAlreadyExistsException]:
        """
        Get the pending CHDAlreadyExistsException from process state

        This is a temporary method during migration.
        In the new architecture, the exception should be in options_context.
        """
        # Check if process has a pending exception attribute
        if hasattr(process, "_pending_exception"):
            return process._pending_exception

        # Check options_context for exception
        if hasattr(process, "last_pending_payload"):
            from rom_management.processing.models import PendingInputPayload

            payload = process.last_pending_payload
            if isinstance(payload, PendingInputPayload) and payload.options_context:
                return payload.options_context.get("exception")

        return None
