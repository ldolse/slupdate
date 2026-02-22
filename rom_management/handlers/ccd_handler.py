from .base import SpecialHandler
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rom_management.processing.models import ResultObject
    from rom_management.processing.base_process import BaseProcess


class CloneCdHandler(SpecialHandler):
    """
    Handler for CloneCD format files.
    Converts CCD files to CUE format for CHD creation.
    """

    def __init__(self):
        super().__init__("CloneCD")

    def validate_preconditions(
        self,
        media: CDMedia,
        file_data: Optional[OpticalMediaProcessor] = None,
        process: Optional["BaseProcess"] = None,
    ) -> "ResultObject":
        """Check if this handler should be applied"""
        from rom_management.processing.models import ResultObject

        ccd_files = [f for f in file_data.file_list if f.suffix.lower() == ".ccd"]
        if len(ccd_files) > 0:
            return ResultObject.success()
        return ResultObject.not_applicable(message="No CCD files found")

    def execute(
        self,
        media: CDMedia,
        file_data: Optional[OpticalMediaProcessor] = None,
        process: Optional["BaseProcess"] = None,
    ) -> "ResultObject":
        """Handle CCD file conversion to CUE format"""
        from rom_management.processing.models import ResultObject

        try:
            # Find CCD files
            ccd_files = [f for f in file_data.file_list if f.suffix.lower() == ".ccd"]
            if not ccd_files:
                return ResultObject.error(
                    error_type="NoCCDFiles",
                    message="No CCD files found in archive",
                )

            # Convert CCD to CUE
            from optical_media.clonecd import ccd_2_cue

            for ccd_file in ccd_files:
                ccd_2_cue(str(ccd_file))

            return ResultObject.success(
                message=f"Converted {len(ccd_files)} CCD file(s) to CUE format"
            )
        except Exception as e:
            return ResultObject.error(
                error_type="CCDConversionError",
                message=f"Failed to convert CCD files: {str(e)}",
                exception=e,
            )

            # Convert CCD to CUE
            from optical_media.clonecd import ccd_2_cue

            for ccd_file in ccd_files:
                ccd_2_cue(str(ccd_file))

            return ResultObject.success(
                message=f"Converted {len(ccd_files)} CCD file(s) to CUE format"
            )
        except Exception as e:
            return ResultObject.error(
                error_type="CCDConversionError",
                message=f"Failed to convert CCD files: {str(e)}",
                exception=e,
            )
