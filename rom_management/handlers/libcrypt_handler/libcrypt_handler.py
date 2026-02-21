import logging
from rom_management.handlers.base import SpecialHandler
from .libcrypt import libcrypt_titles
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor
from rom_management.processing.models import ResultObject

logger = logging.getLogger(__name__)


class LibCryptHandler(SpecialHandler):
    """
    Handle LibCrypt DRM detection for PSX titles.

    LibCrypt only applies to a small subset of PSX Redump titles (~300 of ~2200).
    This handler skips itself for non-matching titles to avoid wasted processing.
    """

    SKIP_CATEGORY = "LibCrypt"

    def __init__(self):
        super().__init__("LibCrypt")

    def validate_preconditions(
        self, media: CDMedia, file_data: OpticalMediaProcessor
    ) -> ResultObject:
        """Check if this handler should be applied to this media.

        LibCrypt only applies to:
        1. PSX platform (guaranteed by platform handler registration)
        2. Redump DAT group
        3. Games with serial numbers that match libcrypt_titles

        Returns:
            - ResultObject.skip() if this is a LibCrypt title (not yet implemented)
            - ResultObject.not_applicable() if not a LibCrypt title (handler not needed)
        """
        if not media.softlist_part or not media.softlist_part.part_of:
            logger.debug(f"LibCrypt: No softlist reference, not applying handler")
            return ResultObject.not_applicable(message="No softlist reference")

        if not media.dat_game_entry or not media.dat_game_entry.dat:
            logger.debug(f"LibCrypt: No DAT reference, not applying handler")
            return ResultObject.not_applicable(message="No DAT reference")

        if media.dat_game_entry.dat.dat_group != "redump":
            logger.debug(f"LibCrypt: Not Redump DAT group, not applying handler")
            return ResultObject.not_applicable(message="Not Redump DAT group")

        serials = media.softlist_part.part_of.serial
        if not serials:
            logger.debug(f"LibCrypt: No serials found, not applying handler")
            return ResultObject.not_applicable(message="No serials found")

        for serial in serials:
            if serial in libcrypt_titles:
                logger.info(f"LibCrypt: Detected LibCrypt title - {serial}")
                return ResultObject.skip(
                    message=f"LibCrypt not yet implemented for {serial}",
                    category=self.SKIP_CATEGORY,
                )

        logger.debug(f"LibCrypt: No matching serials (checked: {serials})")
        return ResultObject.not_applicable(message="Not a LibCrypt title")
