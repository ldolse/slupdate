from typing import Dict, List, Any, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from rom_management.processing.models import Action, ResultObject

if TYPE_CHECKING:
    from consoles import Platform


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
        self._items_iterator = None

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
        """
        Advance to next item after successful step completion.
        Called by execute_step() after _execute_step() returns SUCCESS.
        """
        self.processed_items += 1
        self.current_item = None

    def _handle_skip(self, message: str = "Skipped current item") -> ResultObject:
        """
        Standard skip behavior - clears current item and advances.

        All process SKIP actions should use this method for consistent behavior.
        """
        self.current_item = None
        self.processed_items += 1
        return ResultObject.success(message=message)

    def _handle_skip_all(
        self, message: str = "Skip all remaining items"
    ) -> ResultObject:
        """
        Handle SKIP_ALL action - sets skip_all flag and skips current item.

        All process SKIP_ALL actions should use this method for consistent behavior.
        """
        self.skip_all = True
        return self._handle_skip(message)

    def _post_process(self) -> None:
        """
        Hook for cleanup/save operations after processing completes.
        Called by _complete_process() and _handle_stop().

        Override in subclasses for custom behavior (e.g., save XML).
        Default: pass
        """
        pass

    def _handle_stop(self) -> ResultObject:
        """
        Handle STOP action - calls _post_process then returns COMPLETE.

        Subclasses can override if they need different STOP behavior.
        """
        self._post_process()
        return ResultObject.complete(
            total_processed=self.processed_items,
            stopped_early=True,
        )

    def _complete_process(self) -> ResultObject:
        """
        Called when all items have been processed.
        Calls _post_process() for cleanup/save operations.

        Override in subclasses for custom completion logic.
        """
        self._post_process()
        return ResultObject.complete(total_processed=self.processed_items)

    def execute_step(self) -> ResultObject:
        """
        Execute one step of the process

        Returns:
            ResultObject from executing the step
        """
        # Get next item if we don't have a current item
        if self.current_item is None:
            if not self._get_next_item():
                return self._complete_process()

        result = self._execute_step()

        # Only advance on SUCCESS
        if result.is_success():
            self._advance_after_success()

        return result

    def _get_next_item(self) -> bool:
        """Get next item from iterator - preserves state between calls"""
        if self._items_iterator is None:
            self._items_iterator = iter(self.items_to_process)

        try:
            self.current_item = next(self._items_iterator)
            return True
        except StopIteration:
            self.current_item = None
            return False

    def handle_user_action(
        self, action: "Action", params: Optional[Dict[str, Any]] = None
    ) -> ResultObject:
        """
        Handle user actions from menus

        Args:
            action: The Action enum representing user's choice
            params: Optional parameters for the action

        Returns:
            ResultObject from handling the action
        """
        handler = self._get_handler_for_action(action)

        if handler:
            return handler.execute_action(action, self, params)
        else:
            return self._handle_default_action(action)

    def _get_handler_for_action(self, action: "Action"):
        """
        Find handler for given action type.

        Override in subclasses if needed to map actions to handlers.

        Args:
            action: The Action enum

        Returns:
            Handler instance or None
        """
        return None

    def _handle_default_action(self, action: "Action") -> ResultObject:
        """
        Handle actions not tied to specific handlers

        Args:
            action: The Action enum

        Returns:
            ResultObject from handling the action
        """
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
