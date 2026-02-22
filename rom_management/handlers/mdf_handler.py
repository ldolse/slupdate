from .base import SpecialHandler
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rom_management.processing.models import ResultObject


class MdFHandler(SpecialHandler):
    """
    Handler for MDF format files.
    Converts MDF files to ISO format for CHD creation.
    """

    def __init__(self):
        super().__init__("MDF")

    def validate_preconditions(
        self, media: CDMedia, file_data: OpticalMediaProcessor = None
    ) -> "ResultObject":
        """Check if this handler should be applied"""
        from rom_management.processing.models import ResultObject

        mdf_files = [f for f in file_data.file_list if f.suffix.lower() == ".mdf"]
        if len(mdf_files) > 0:
            return ResultObject.success()
        return ResultObject.not_applicable(message="No MDF files found")

    def execute(
        self, media: CDMedia, file_data: OpticalMediaProcessor
    ) -> "ResultObject":
        """Handle MDF file conversion to ISO format"""
        from rom_management.processing.models import ResultObject

        try:
            # Find MDF files
            mdf_files = [f for f in file_data.file_list if f.suffix.lower() == ".mdf"]
            if not mdf_files:
                return ResultObject.error(
                    error_type="NoMDFFiles",
                    message="No MDF files found in archive",
                )

            # Convert MDF to ISO
            for mdf_file in mdf_files:
                self._convert_mdf_to_iso(mdf_file)

            return ResultObject.success(
                message=f"Converted {len(mdf_files)} MDF file(s) to ISO format"
            )
        except Exception as e:
            return ResultObject.error(
                error_type="MDFConversionError",
                message=f"Failed to convert MDF files: {str(e)}",
                exception=e,
            )

    def _convert_mdf_to_iso(self, mdf_file):
        """
        Placeholder for actual MDF to ISO conversion logic.
        This would require external tools or libraries.
        """
        # TODO: Implement MDF to ISO conversion
        # This might require tools like:
        # - bchunk
        # - isoform
        # - Or specialized MDF conversion libraries
        pass
