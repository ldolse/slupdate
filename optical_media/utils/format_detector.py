from rom_management.handlers import SpecialHandler
from optical_media.clonecd import CCDHandler
from optical_media.bincue import BinCueHandler
import os

from typing import Optional

class FormatDetector:
    @staticmethod
    def detect_format(file_path: str) -> Optional[str]:
        """Detect the format of optical media files"""
        # Logic to determine file type and required handling
        pass

    @staticmethod
    def get_handler(directory: str) -> Optional[SpecialHandler]:
        """Get appropriate handler for detected format"""
        format_type = FormatDetector.detect_format(directory)
        return {
            'ccd': CCDHandler(),
            'bin_cue': BinCueHandler(),
            # ... other formats
        }.get(format_type, None)

    def find_toc_file(self, directory: str) -> Optional[str]:
        """
        Not sure if this belongs here with the new get_handler logic
        Find TOC file (cue/gdi/iso) in extracted directory
        Returns path to TOC file or None
        """
        for filename in os.listdir(directory):
            if filename.lower().endswith(('.cue', '.gdi')):
                return os.path.join(directory, filename)

        iso_files = [f for f in os.listdir(directory) if f.lower().endswith('.iso')]
        if len(iso_files) == 1:
            return os.path.join(directory, iso_files[0])

        return None

    def prepare_for_chd(self, directory: str) -> Optional[str]:
        """
        Prepare extracted files for CHD conversion
        Returns path to TOC file or None on error
        this function is likely deprecated and replaced with (or moved to) get_handler logic
        """
        toc_file = self.find_toc_file(directory)

        if not toc_file:
            # Handle special cases (no-intro, etc.)
            # this is old version - replaced with new logic delete once confirmed working
            return self.handle_special_cases(directory)

        return toc_file