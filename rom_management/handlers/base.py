from abc import ABC, abstractmethod
from ..exceptions import UserActionRequiredException, SkipCurrentItemException, HandlerException
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor

class SpecialHandler(ABC):
    def __init__(self, name: str, menu=None):
        self.name = name
        self.menu = menu  # Associated menu for user interaction

    @abstractmethod
    def _handle(self, exception: Exception, process) -> dict:
        """Handle special case processing, override in subclasses"""
        pass

    def handle(self, exception: Exception, process) -> dict:
        """Handle special processing with exception-based error handling"""
        try:
            return self._handle(exception, process)
        except Exception as e:
            # Convert specific exceptions to our handler exception hierarchy
            if self._requires_user_intervention(e):
                raise UserActionRequiredException(
                    f"Handler {self.name} requires user action: {str(e)}",
                    menu_name=self.menu.name if self.menu else "handler_error_menu"
                )
            elif self._should_skip_item(e):
                raise SkipCurrentItemException(f"Handler {self.name} skipping item: {str(e)}")
            else:
                raise HandlerException(f"Handler {self.name} failed: {str(e)}")

    def validate_preconditions(self, media: CDMedia, file_data: OpticalMediaProcessor) -> bool:
        """Check if this handler should be applied"""
        return True

    def _requires_user_intervention(self, error: Exception) -> bool:
        """Override in subclasses to determine if user intervention is needed"""
        return False

    def _should_skip_item(self, error: Exception) -> bool:
        """Override in subclasses to determine if item should be skipped"""
        return False
        
    def get_menu_name(self) -> str:
        """Get the menu name associated with this handler for user interaction"""
        return self.menu.name if self.menu else "handler_error_menu"
