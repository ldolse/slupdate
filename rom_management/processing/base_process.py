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

    def execute_step(self) -> ResultObject:
        """
        Execute one step of the process

        Returns:
            ResultObject from executing the step
        """
        # Get next item if we don't have a current item
        if self.current_item is None:
            if not self._get_next_item():
                return ResultObject.complete(total_processed=self.processed_items)

        result = self._execute_step()

        # Only advance on SUCCESS
        if result.is_success():
            self.processed_items += 1
            self.current_item = None

        return result

    def _get_next_item(self) -> bool:
        """Get next item from iterator - preserves state between calls"""
        if self._items_iterator is None:
            # Initialize iterator if not already done
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
        # Find handler for this action type
        handler = self._get_handler_for_action(action)

        if handler:
            return handler.execute_action(action, self, params)
        else:
            # Handle default actions
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
            return ResultObject.complete(
                total_processed=self.processed_items,
                stopped_early=True,
            )
        elif action == Action.CONTINUE:
            self.current_item = None
            return ResultObject.success(
                message="Continuing to next item",
            )
        elif action == Action.SKIP:
            self.current_item = None
            return ResultObject.success(
                message="Skipped current item",
            )

        return ResultObject.complete(
            total_processed=self.processed_items,
            stopped_early=True,
        )

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
        # Reset iterator when new items are set
        self._items_iterator = None
