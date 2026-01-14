from rom_management import ZipProcessor
from media_registry import CDMedia
from pathlib import Path
from typing import Optional, Iterator

class OpticalMediaProcessor:
    def __init__(self, media: CDMedia, tmpdsk: Optional[str] = None):
        """
        Initialize processor for optical media conversion

        Args:
            zip_path: Path to the source ZIP file
            temp_dir: Base directory for temp files (defaults to system temp)
        """
        self.zip_path = media.zip_path
        self.media = media
        self.tmpdsk = tmpdsk
        self.temp_dir: Optional[Path] = None
        self.current_toc: Optional[Path] = None
        self.filedata: Optional[ZipProcessor] = None
        self.format: Optional[str] = None

    @property
    def file_list(self) -> Iterator[Path]:
        """Returns an iterator of all files in the temp directory"""
        if not self.temp_dir or not self.temp_dir.exists():
            return iter([])

        return (item for item in self.temp_dir.iterdir() if item.is_file())

    def extract_and_process(self) -> 'OpticalMediaProcessor':
        self.filedata = ZipProcessor(tmpdsk=self.tmpdsk)
        try:
            self.temp_dir = self.filedata.extract_to_tempdir(self.zip_path)
        except Exception as e:
            raise RuntimeError(f"Failed to extract {self.zip_path} ZIP file: {e}")
        # Initial TOC detection
        self._detect_toc()
        self._detect_format()

    def _detect_toc(self) -> None:
        """Detect the primary TOC file in the extracted contents"""
        # todo: add checking / exception handling for multiple toc files

        # Look for standard TOC files supported by chdman
        for f in self.file_list:
            if f.suffix.lower() in ('.cue', '.gdi', '.toc'):
                self.current_toc = f
                return

        # Look for single ISO files
        iso_files = [f for f in self.file_list if f.suffix.lower() == '.iso']
        if len(iso_files) == 1:
            self.current_toc = iso_files[0]
            return
        if len(iso_files) > 1:
            print("Multiple ISO files found; cannot determine TOC.")
            return

        # Look for CCD files (these will need conversion)
        ccd_files = [f for f in self.file_list if f.suffix.lower() == '.ccd']
        if ccd_files:
            self.current_toc = ccd_files[0]

    def _detect_format(self) -> None:
        """Get the format type based on current TOC and files"""
        if not self.current_toc:
            return None

        if self.current_toc.suffix.lower() == '.cue':
            # Check if it's a simple bin/cue or needs special handling
            self.format = 'cue'
        elif self.current_toc.suffix.lower() == '.gdi':
            self.format = 'gdi'
        elif self.current_toc.suffix.lower() == '.ccd':
            self.format =  'ccd'
        elif self.current_toc.suffix.lower() == '.iso':
            return 'iso'
        elif self.current_toc.suffix.lower() == '.toc':
            self.format = 'toc'
        elif self.current_toc.suffix.lower() == '.mds':
            self.format = 'mds'

        return None

    def _analyze_cue_format(self) -> str:
        """Analyze CUE file format for special cases"""
        try:
            with open(self.current_toc, 'r') as f:
                contents = f.read()

            # Check for no-intro style issues
            if 'FILE "file.bin"' in contents:
                return 'cue_needs_filename_fix'

            # Check for other special cases
            if 'MODE2/2352' in contents:
                return 'cue_mode2_2352'

            return 'standard_bin_cue'

        except Exception:
            return 'cue_parse_error'

    def update_toc(self, new_toc_path: str) -> None:
        """Update the current TOC reference"""
        self.current_toc = Path(new_toc_path)

    def refresh_toc(self) -> None:
        """Refresh TOC detection after file modifications"""
        self._detect_toc()

    def get_temp_dir(self) -> Path:
        """Get the temp directory path"""
        if not self.temp_dir:
            raise RuntimeError("Processor not initialized. Call extract_and_process() first.")
        return self.temp_dir

    def get_toc(self) -> Optional[Path]:
        """Get the current TOC file"""
        return self.current_toc

    def get_file(self, filename: str) -> Optional[Path]:
        """Get a specific file from the extracted contents"""
        return self.file_list.get(filename)

    def cleanup(self) -> None:
        """Clean up temp directory"""
        if self.temp_dir and self.temp_dir.exists():
            self.filedata.cleanup_tempdir()
            self.temp_dir = None
            self.current_toc = None
            self.filedata = None