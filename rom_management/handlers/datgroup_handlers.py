from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor
from .base import SpecialHandler
from rom_management.processing.models import ResultObject
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rom_management.processing.base_process import BaseProcess


class RedumpHandler(SpecialHandler):
    def __init__(self):
        super().__init__("Redump")

    def validate_preconditions(
        self,
        media: CDMedia,
        file_data: Optional[OpticalMediaProcessor] = None,
        process: Optional["BaseProcess"] = None,
    ) -> ResultObject:
        return ResultObject.not_applicable()


class NoIntroHandler(SpecialHandler):
    def __init__(self):
        super().__init__("NoIntro")

    def validate_preconditions(
        self,
        media: CDMedia,
        file_data: Optional[OpticalMediaProcessor] = None,
        process: Optional["BaseProcess"] = None,
    ) -> ResultObject:
        return ResultObject.not_applicable()
