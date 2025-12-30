from .base import SpecialHandler
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rom_management.processing.models import ResultObject


class BinCueHandler(SpecialHandler):
    """
    Handler for BIN/CUE format files.
    Ensures CUE files reference correct bin filenames.
    """

    def __init__(self):
        super().__init__("BinCue")

    def validate_preconditions(
        self, media: CDMedia, file_data: OpticalMediaProcessor
    ) -> bool:
        """Check if this handler should be applied"""
        # Verify we have bin/cue files
        cue_files = [f for f in file_data.file_list if f.suffix.lower() == ".cue"]
        bin_files = [f for f in file_data.file_list if f.suffix.lower() == ".bin"]

        return len(cue_files) > 0 and len(bin_files) > 0

    def execute(
        self, media: CDMedia, file_data: OpticalMediaProcessor
    ) -> "ResultObject":
        """Handle bin/cue processing"""
        from rom_management.processing.models import ResultObject

        try:
            # Find CUE files
            cue_files = [f for f in file_data.file_list if f.suffix.lower() == ".cue"]
            if not cue_files:
                return ResultObject.error(
                    error_type="NoCUEFiles",
                    message="No CUE files found in archive",
                )

            # Process cue files to ensure correct references
            for cue_file in cue_files:
                self._fix_cue_file_references(cue_file)

            return ResultObject.success(
                message=f"Validated {len(cue_files)} CUE file(s)"
            )
        except Exception as e:
            return ResultObject.error(
                error_type="CUEProcessingError",
                message=f"Failed to process CUE files: {str(e)}",
                exception=e,
            )

    def _fix_cue_file_references(self, cue_file):
        """Fix CUE file to reference correct bin filenames"""
        from pathlib import Path

        try:
            with open(cue_file, "r") as f:
                content = f.read()

            # Check if CUE references standard "file.bin" (common no-intro issue)
            if 'FILE "file.bin"' in content:
                # Find actual bin filename in directory
                cue_dir = Path(cue_file).parent
                bin_file = cue_dir / "file.bin"
                if bin_file.exists():
                    # Update CUE to reference actual bin file
                    content = content.replace(
                        'FILE "file.bin"', f'FILE "{bin_file.name}"'
                    )

                    with open(cue_file, "w") as f:
                        f.write(content)
        except Exception:
            # If we can't process it, CHDman will likely error anyway
            pass
