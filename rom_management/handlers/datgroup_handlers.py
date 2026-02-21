from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor as file_data
from .base import SpecialHandler
from rom_management.processing.models import ResultObject


class RedumpHandler(SpecialHandler):
    def __init__(self):
        super().__init__("Redump")

    def handle(self, media: CDMedia, file_data: file_data) -> dict:
        # Handle redump-specific logic
        pass

    def validate_preconditions(
        self, media: CDMedia, file_data: file_data
    ) -> ResultObject:
        return ResultObject.success()


class NoIntroHandler(SpecialHandler):
    def __init__(self):
        super().__init__("NoIntro")

    def handle(self, media: CDMedia, file_data: file_data) -> dict:
        # Handle no-intro-specific logic
        pass

    def validate_preconditions(
        self, media: CDMedia, file_data: file_data
    ) -> ResultObject:
        return ResultObject.success()
