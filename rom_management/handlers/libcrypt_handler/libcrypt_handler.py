import logging
from rom_management.handlers.base import SpecialHandler
from .libcrypt import libcrypt_titles
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor

logger = logging.getLogger(__name__)


class LibCryptHandler(SpecialHandler):
    """
    Handle LibCrypt DRM detection for PSX titles.

    LibCrypt only applies to a small subset of PSX Redump titles (~300 of ~2200).
    This handler skips itself for non-matching titles to avoid wasted processing.
    """

    def __init__(self):
        super().__init__("LibCrypt")

    def handle(self, media: CDMedia, file_data: OpticalMediaProcessor) -> dict:
        """Handle libcrypt DRM insertion"""
        try:
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def validate_preconditions(
        self, media: CDMedia, file_data: OpticalMediaProcessor
    ) -> bool:
        """Check if this handler should be applied to this media.

        LibCrypt only applies to:
        1. PSX platform (guaranteed by platform handler registration)
        2. Redump DAT group
        3. Games with serial numbers that match libcrypt_titles

        Returns:
            True only for known LibCrypt titles (~14% of PSX Redump games)
        """
        if not media.softlist_part or not media.softlist_part.part_of:
            logger.debug(f"LibCrypt: Skipping {media.id} - no softlist part reference")
            return False

        if not media.dat_game_entry or not media.dat_game_entry.dat:
            logger.debug(f"LibCrypt: Skipping {media.id} - no DAT reference")
            return False

        if media.dat_game_entry.dat.dat_group != "redump":
            logger.debug(
                f"LibCrypt: Skipping {media.id} - not Redump (group: {media.dat_game_entry.dat.dat_group})"
            )
            return False

        serials = media.softlist_part.part_of.serial
        if not serials:
            logger.debug(f"LibCrypt: Skipping {media.id} - no serials found")
            return False

        for serial in serials:
            if serial in libcrypt_titles:
                logger.debug(
                    f"LibCrypt: Applying to {media.id} - matched serial {serial}"
                )
                return True

        logger.debug(
            f"LibCrypt: Skipping {media.id} - no matching serials (checked: {serials})"
        )
        return False
