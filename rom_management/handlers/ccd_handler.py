from .base import SpecialHandler
from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor

class CloneCdHandler(SpecialHandler):
    def __init__(self):
        super().__init__("CloneCD")

    def validate_preconditions(self, media: CDMedia, file_data: OpticalMediaProcessor) -> bool:
        """Check if this handler should be applied"""
        # Check media metadata
        if hasattr(media, 'format_type') and media.format_type != 'ccd':
            return False

        # Verify we have CCD files
        ccd_files = [f for f in file_data.file_list if f.suffix.lower() == '.ccd']
        return len(ccd_files) > 0

    def handle(self, media: CDMedia, file_data: OpticalMediaProcessor) -> dict:
        """Handle CCD file conversion"""
        try:
            # Find CCD files
            ccd_files = [f for f in file_data.file_list if f.suffix.lower() == '.ccd']
            if not ccd_files:
                return {'success': False, 'error': 'No CCD files found'}

            # Convert CCD to CUE
            for ccd_file in ccd_files:
                from optical_media.clonecd import ccd_2_cue
                ccd_2_cue(str(ccd_file), str(file_data.temp_dir))

            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}




