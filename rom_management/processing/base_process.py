from typing import Dict, List, Any, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from consoles import Platform

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
            'process_metadata': {},
            'user_preferences': {}
        }
        self.current_item = None

    @abstractmethod
    def initialize(self):
        """Initialize the process - should be overridden"""
        pass

    @abstractmethod
    def _execute_step(self) -> dict:
        """Execute one step of the process - should be overridden"""
        pass

    def execute_step(self) -> dict:
        """Execute one step of the process with exception handling"""
        if self.state['current_index'] >= self.state['total_items']:
            return {'complete': True}
        
        self.set_current_item()
        
        try:
            result = self._execute_step()
            
            # If successful, advance to next item
            if result.get('success'):
                self.state['current_index'] += 1
                
            return {'continue': True}
            
        except Exception as e:
            # Handle exceptions using the handler system
            return self._handle_exception(e)

    def _handle_exception(self, exception: Exception) -> dict:
        """Handle exceptions using the handler system"""
        # Find a handler for this exception
        handler = self.platform.process_manager.get_handler_for_exception(exception, self.current_item)
        
        if handler:
            try:
                # Let the handler try to resolve the exception
                result = handler.handle(self.current_item, None)
                
                if isinstance(result, dict):
                    return result
                else:
                    # Handler resolved the exception, continue processing
                    return {'continue': True}
            except Exception as e:
                # If handler can't resolve, re-raise for menu handling
                if hasattr(e, 'menu_class_name'):
                    return {
                        'needs_user_input': True,
                        'menu': e.menu_class_name,
                        'payload': self
                    }
                else:
                    # Re-raise the original exception for generic handling
                    raise e
        else:
            # No handler found, re-raise to be handled by generic error handling
            raise exception

    def handle_user_action(self, action: str) -> dict:
        """Handle user actions from menus - should be overridden by subclasses"""
        raise NotImplementedError("Subclasses must implement handle_user_action")

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

    def is_complete(self) -> bool:
        """Check if process is complete"""
        return self.state['current_index'] >= self.state['total_items']

    def advance_to_next_item(self):
        """Advance to the next item"""
        self.state['current_index'] += 1
