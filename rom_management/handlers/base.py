from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING
from ..exceptions import (
    UserActionRequiredException,
    SkipCurrentItemException,
    HandlerException,
)
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
    ) -> bool:
        """Check if this handler should be applied"""
        return True

    def _requires_user_intervention(self, error: Exception) -> bool:
        """
        Override in subclasses to determine if user intervention is needed

        DEPRECATED: Not used in new architecture.
        """
        return False

    def _should_skip_item(self, error: Exception) -> bool:
        """
        Override in subclasses to determine if item should be skipped

        DEPRECATED: Not used in new architecture.
        """
        return False

    def get_menu_name(self) -> str:
        """
        Get the menu name associated with this handler for user interaction

        DEPRECATED: MenuSystem now manages query handlers directly.
        """
        return self.menu.name if self.menu else "handler_error_menu"

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
            ResultObject from executing the action

        DEPRECATED: Use execute_action() in subclasses. This default implementation
        raises NotImplementedError.
        """
        from rom_management.processing.models import ResultObject

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

        DEPRECATED: Use execute() in subclasses. This default implementation
        raises NotImplementedError.
        """
        from rom_management.processing.models import ResultObject

        raise NotImplementedError(
            f"Handler {self.name} must implement execute() "
            "if it performs automated processing"
        )
        """
        Execute an action for this handler.

        This is used by interactive handlers that respond to user actions
        (e.g., MD5ScanHandler, CHDExistenceHandler).

        Args:
            action: The Action enum representing user's choice
            process: The BaseProcess instance
            params: Optional parameters for the action

        Returns:
            ResultObject from executing the action

        DEPRECATED: Use execute_action() in subclasses. This default implementation
        raises NotImplementedError.
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

        DEPRECATED: Use execute() in subclasses. This default implementation
        raises NotImplementedError.
        """
        from rom_management.processing.models import ResultObject

        raise NotImplementedError(
            f"Handler {self.name} must implement execute() "
            "if it performs automated processing"
        )
