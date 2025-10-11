from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor
from .base import SpecialHandler

class BinCueHandler(SpecialHandler):
    def __init__(self):
        super().__init__("BinCue")

    def validate_preconditions(self, media: CDMedia, file_data: OpticalMediaProcessor) -> bool:
        """Check if this handler should be applied"""
        # Check media metadata first
        if hasattr(media, 'format_type') and media.format_type != 'bin_cue':
            return False

        # Verify we actually have bin/cue files
        cue_files = [f for f in file_data.file_list if f.suffix.lower() == '.cue']
        bin_files = [f for f in file_data.file_list if f.suffix.lower() == '.bin']

        return len(cue_files) > 0 and len(bin_files) > 0

    def handle(self, media: CDMedia, file_data: OpticalMediaProcessor) -> dict:
        """Handle bin/cue processing"""
        try:
            # Find CUE files
            cue_files = [f for f in file_data.file_list if f.suffix.lower() == '.cue']
            if not cue_files:
                return {'success': False, 'error': 'No CUE files found'}

            # Process cue files
            for cue_file in cue_files:
                self._process_cue_file(cue_file, file_data.temp_dir)

            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
