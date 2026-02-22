from typing import Dict, List, Any, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from rom_management.processing.models import Action, ResultObject
import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from consoles import Platform
    from rom_management.handlers.base import SpecialHandler


class BaseProcess(ABC):
    """
    Base class for long-running processes that may require user interaction.

    Processes manage their own state and use ResultObject for communication.
    Exception-based control flow has been removed - processes return
    ResultObject.pending_input() when user interaction is needed.
    """

    def __init__(self, platform: "Platform"):
        self.platform = platform
        self.total_items = 0
        self.processed_items = 0
        self.current_item = None
        self.items_to_process = []
        self.skip_all = False
        self._skipped_categories: set[str] = (
            set()
        )  # Track skipped categories for contextual SKIP_ALL
        self._items_iterator = None
        self._timeout_seconds = 30
        self._skip_handler_check = (
            False  # Flag to skip handler check when handler is executing step
        )

    @abstractmethod
    def initialize(self):
        """Initialize the process - should be overridden"""
        pass

    @abstractmethod
    def register_handlers(self):
        """
        Register handlers for this process type.

        This method is for clarity during process setup.
        Handlers are now called directly by processes, not via exceptions.
        """
        pass

    @abstractmethod
    def _execute_step(self) -> ResultObject:
        """
        Execute one step of the process - should be overridden

        Returns:
            ResultObject indicating step result (SUCCESS, PENDING_INPUT, COMPLETE, ERROR)
        """
        pass

    def _advance_after_success(self) -> None:
        """Advance to next item after successful step completion"""
        self.processed_items += 1
        self.current_item = None

    def _handle_skip(self, message: str = "Skipped current item") -> ResultObject:
        """Standard skip behavior - clears current item and advances"""
        logger.info(f"SKIP: {message}")
        self.current_item = None
        self.processed_items += 1
        return ResultObject.success(message=message)

    def _handle_skip_all(
        self, message: str = "Skip all remaining items", category: Optional[str] = None
    ) -> ResultObject:
        """Handle SKIP_ALL action - sets skip_all flag and skips current item"""
        logger.info(f"SKIP_ALL: {message}")
        self.skip_all = True
        if category:
            self._skipped_categories.add(category)
        return self._handle_skip(message)

    def _post_process(self) -> None:
        """Hook for cleanup/save operations after processing completes"""
        pass

    def _handle_stop(self) -> ResultObject:
        """Handle STOP action - calls _post_process then returns COMPLETE"""
        logger.info(f"STOP: Processed {self.processed_items} items")
        self._post_process()
        return ResultObject.complete(
            total_processed=self.processed_items,
            stopped_early=True,
        )

    def _complete_process(self) -> ResultObject:
        """Called when all items have been processed"""
        logger.info(f"Process complete: {self.processed_items} items processed")
        self._post_process()
        return ResultObject.complete(total_processed=self.processed_items)

    def execute_step(self) -> ResultObject:
        """Execute one step of the process"""
        logger.debug(
            f"execute_step: processed={self.processed_items}, total={self.total_items}"
        )

        if self.current_item is None:
            if not self._get_next_item():
                return self._complete_process()

        result = self._execute_step()

        if result.is_success():
            self._advance_after_success()
            logger.debug(f"Advanced: processed={self.processed_items}")

        return result

    def _get_next_item(self) -> bool:
        """Get next item from iterator - preserves state between calls"""
        if self._items_iterator is None:
            self._items_iterator = iter(self.items_to_process)
            logger.debug(f"Iterator created with {len(self.items_to_process)} items")

        try:
            self.current_item = next(self._items_iterator)
            return True
        except StopIteration:
            self.current_item = None
            return False

    def handle_user_action(
        self, action: "Action", params: Optional[Dict[str, Any]] = None
    ) -> ResultObject:
        """Handle user actions from menus"""
        handler = self._get_handler_for_action(action)

        if handler:
            return handler.execute_action(action, self, params)
        else:
            return self._handle_default_action(action)

    def _get_handler_for_action(self, action: "Action") -> "Optional[SpecialHandler]":
        """Find handler for given action type"""
        return None

    def _handle_default_action(self, action: "Action") -> ResultObject:
        """Handle actions not tied to specific handlers"""
        if action == Action.STOP:
            return self._handle_stop()
        elif action == Action.CONTINUE:
            self.current_item = None
            return ResultObject.success(
                message="Continuing to next item",
            )
        elif action == Action.SKIP:
            return self._handle_skip("Skipped current item")

        return self._handle_stop()

    def get_progress(self) -> dict:
        """Return current progress information"""
        return {
            "processed": self.processed_items,
            "total": self.total_items,
            "percentage": self._calculate_progress_percentage(),
        }

    def _calculate_progress_percentage(self) -> float:
        """Calculate progress percentage"""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100

    def set_items_to_process(self, items: List[Any]):
        """Set the list of items to process"""
        self.items_to_process = items
        self.total_items = len(items)
        self._items_iterator = None
        logger.debug(f"Items set: {len(items)} total")
