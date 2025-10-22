from typing import Dict, List, Any, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from consoles import Platform

class BaseProcess(ABC):
    """Base class for long-running processes that may require user interaction"""

    def __init__(self, platform: 'Platform'):
        self.platform = platform
        # Direct attributes instead of nested dict
        self.total_items = 0
        self.processed_items = 0
        self.current_item = None
        self.exception_payload = None
        self.items_to_process = []

        # Common preferences that all processes might need
        self.skip_all = False

        self._handling_exception = False
        self.handlers = {}  # Exception type -> handler mapping
        self._items_iterator = None

    @abstractmethod
    def initialize(self):
        """Initialize the process - should be overridden"""
        pass

    @abstractmethod
    def register_handlers(self):
        """Register handlers for this process type - should be overridden"""
        pass

    @abstractmethod
    def _execute_step(self) -> dict:
        """Execute one step of the process - should be overridden"""
        pass

    def execute_step(self) -> dict:
        """Execute one step of the process with exception handling"""

        # Only get next item if we don't have a current item (i.e., starting fresh)
        if self.current_item is None:
            if not self._get_next_item():
                return {'complete': True}

        try:
            result = self._execute_step()

            # Only advance if processing was successful
            if result.get('success', True):
                self.processed_items += 1
                # Clear current_item to indicate we're done with it
                self.current_item = None

            return result

        except Exception as e:
            # Handle exceptions using the handler system
            return self._handle_exception(e)

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

    def _handle_exception(self, exception: Exception) -> dict:
        """Handle exceptions using the handler system"""
        # Prevent recursion by checking if we're already handling an exception
        if self._handling_exception:
            # We're already in exception handling - just return an error
            return {'needs_user_input': True, 'menu': 'error_menu', 'payload': str(exception)}

        self._handling_exception = True

        try:
            # Find a handler for this exception type
            handler = self.handlers.get(type(exception))

            if handler:
                try:
                    # Let the handler deal with this exception
                    result = handler.handle(exception, self)

                    if isinstance(result, dict):
                        return result
                    else:
                        # Handler resolved the exception, continue processing
                        self._handling_exception = False
                        return {'continue': True}
                except Exception as e:
                    # If handler can't resolve, re-raise for menu handling
                    if hasattr(e, 'menu_class_name'):
                        self._handling_exception = False
                        raise e  # Re-raise the exception with menu_class_name
                    else:
                        # Re-raise the original exception for generic handling
                        raise e
            else:
                # No handler found, re-raise to be handled by generic error handling
                raise exception
        finally:
            self._handling_exception = False

    def handle_user_action(self, action: str) -> dict:
        """Handle user actions from menus"""
        # Get current exception if any
        current_exception = self.exception_payload

        if current_exception and type(current_exception) in self.handlers:
            # Delegate to handler for this exception type
            return self.handlers[type(current_exception)].handle_user_action(action, self)
        else:
            # Default handling for actions not tied to specific exceptions
            return self._handle_default_user_action(action)

    def _handle_default_user_action(self, action: str) -> dict:
        """Handle user actions not tied to specific exceptions"""
        if action == 'stop':
            return {'complete': True, 'stopped_early': True}
        # Default behavior - don't advance index
        return {'success': False}

    def get_progress(self) -> dict:
        """Return current progress information"""
        return {
            'processed': self.processed_items,
            'total': self.total_items,
            'percentage': self._calculate_progress_percentage()
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

