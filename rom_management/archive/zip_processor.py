import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from dat.rom_dat import GameEntry as DATGameEntry
from typing import Optional, Dict

class ZipProcessor:
    def __init__(self, tmpdsk: Optional[str] = None):
        self.tmpdsk = tmpdsk if tmpdsk else tempfile.gettempdir()
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
            self.temp_dir = tempfile.mkdtemp(dir=self.tmpdsk)
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                for file_info in zip_file.infolist():
                    if not file_info.filename.startswith('__MACOSX/'):
                        zip_file.extract(file_info, self.temp_dir)
            return Path(self.temp_dir)
        except Exception as e:
            print(f"Extraction error: {e}")
            self.cleanup_tempdir()
            return None

    def cleanup_tempdir(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)