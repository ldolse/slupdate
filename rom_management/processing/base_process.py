from typing import Dict, List, Any, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from consoles import Platform

# Use string annotation for type hints to avoid circular imports
class BaseProcess(ABC):
    """Base class for long-running processes that may require user interaction"""

    def __init__(self, platform: 'Platform'):
        self.platform = platform
        self.state = {
            'current_index': 0,
            'total_items': 0,
            'current_item': None,
            'exception_payload': None,
            'items_to_process': [],
            'process_metadata': {}
        }
        self.current_item = None
        self.user_preference = None  # Can be "skip_all", "continue_all", or None

    @abstractmethod
    def initialize(self):
        """Initialize the process - should be overridden"""
        pass

    @abstractmethod
    def _execute_step(self) -> dict:
        """Execute one step of the process - should be overridden"""
        pass

    def execute_step(self) -> dict:
        """Execute one step of the process, base function"""
        if self.state['current_index'] >= self.state['total_items']:
            return {'complete': True}
        self.set_current_item()
        result = self._execute_step()
        return result

    @abstractmethod
    def handle_user_action(self, action: str) -> dict:
        """Handle user actions after exceptions - should be overridden"""
        pass

    def get_progress(self) -> dict:
        """Return current progress information"""
        return {
            'current': self.state['current_index'],
            'total': self.state['total_items'],
            'percentage': self._calculate_progress_percentage()
        }

    def _calculate_progress_percentage(self) -> float:
        """Calculate progress percentage"""
        if self.state['total_items'] == 0:
            return 0.0
        return (self.state['current_index'] / self.state['total_items']) * 100

    def set_current_item(self) -> None:
        """Get the current item being processed"""
        if 0 <= self.state['current_index'] < len(self.state['items_to_process']):
            self.current_item = self.state['items_to_process'][self.state['current_index']]
        return None

    def set_items_to_process(self, items: List[Any]):
        """Set the list of items to process"""
        self.state['items_to_process'] = items
        self.state['total_items'] = len(items)
