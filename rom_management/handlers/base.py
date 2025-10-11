from abc import ABC, abstractmethod
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor

class SpecialHandler(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def handle(self, media: CDMedia, file_data: OpticalMediaProcessor) -> dict:
        """Handle special case processing"""
        pass

    def validate_preconditions(self, media: CDMedia, file_data: OpticalMediaProcessor) -> bool:
        """Check if this handler should be applied"""
        return True