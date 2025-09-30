import os
import zipfile
import tempfile
import shutil
from dat.rom_dat import GameEntry as DATGameEntry
from typing import Optional

class ZipProcessor:
    def __init__(self):
        self.temp_dir = None
        self.extracted_files = []

    def find_valid_zip(self, dat_entry: 'DATGameEntry', rom_dir: str) -> Optional[str]:
        """
        Find and validate zip file for a DAT entry
        Returns path to valid zip or None
        """
        zip_name = f"{dat_entry.name}.zip"
        zip_path = os.path.join(rom_dir, zip_name)

        if not os.path.isfile(zip_path):
            print(f"Zip file does not exist: {zip_path}")
            return None

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                for rom in dat_entry.roms:
                    if rom.name not in zip_file.namelist():
                        return None
                    zip_info = zip_file.getinfo(rom.name)
                    if rom.crc and zip_info.CRC != int(rom.crc, 16):
                        return None
                    elif rom.md5 and not rom.crc:
                        # temporary prompt for MD5 check if CRC not available
                        user_input = input("   Check Using MD5? (y/n): ").strip().lower()
                        if user_input != 'y':
                            return None
                        # MD5 check if CRC not available
                        import hashlib
                        md5_hash = hashlib.md5()
                        with zip_file.open(rom.name) as f:
                            for chunk in iter(lambda: f.read(4096), b""):
                                md5_hash.update(chunk)
                        if md5_hash.hexdigest().lower() != rom.md5.lower():
                            return None

            return zip_path
        except (zipfile.BadZipFile, KeyError):
            return None

    def extract_to_tempdir(self, zip_path: str) -> Optional[str]:
        """
        Extract zip to temp directory
        Returns path to temp dir or None on error
        """
        try:
            self.temp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                for file_info in zip_file.infolist():
                    if not file_info.filename.startswith('__MACOSX/'):
                        zip_file.extract(file_info, self.temp_dir)
            return self.temp_dir
        except Exception as e:
            print(f"Extraction error: {e}")
            self.cleanup()
            return None

    def find_toc_file(self, directory: str) -> Optional[str]:
        """
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
        """
        toc_file = self.find_toc_file(directory)

        if not toc_file:
            # Handle special cases (no-intro, etc.)
            return self.handle_special_cases(directory)

        return toc_file

    def handle_special_cases(self, directory: str) -> Optional[str]:
        """
        Handle special cases like no-intro DATs
        Returns path to TOC file or None
        """
        # Implementation for special cases (similar to original special_rom_handling)
        pass

    def cleanup_tempdir(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)