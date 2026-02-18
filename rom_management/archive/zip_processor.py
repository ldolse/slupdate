import os
import zipfile
import tempfile
import shutil
import logging
import threading
from pathlib import Path
from dat.rom_dat import GameEntry as DATGameEntry
from typing import Optional, Dict, Callable, Any

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when an operation exceeds the timeout"""

    pass


def with_timeout(seconds: int):
    """Decorator to add timeout to a function using threading"""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            result: Any = [None]
            exception: Optional[Exception] = None

            def target():
                nonlocal exception
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(seconds)

            if thread.is_alive():
                raise TimeoutError(f"Operation timed out after {seconds}s")
            if exception is not None:
                raise exception
            return result[0]

        return wrapper

    return decorator


def calculate_timeout(
    file_path: str, base_seconds: int = 60, mb_per_second: float = 10.0
) -> int:
    """Calculate timeout based on file size and estimated network speed"""
    try:
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        return int(base_seconds + (size_mb / mb_per_second))
    except OSError:
        return base_seconds


class MD5ScanRequiredException(Exception):
    """Raised when MD5 scanning is required for validation"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ZipProcessor:
    def __init__(self, tmpdsk: Optional[str] = None):
        self.tmpdsk = tmpdsk if tmpdsk else tempfile.gettempdir()
        self.extracted_files = []

    @with_timeout(30)
    def find_valid_zip(
        self, dat_entry: "DATGameEntry", rom_dir: str, md5=False
    ) -> Optional[str]:
        """Find and validate zip file for a DAT entry"""
        zip_name = f"{dat_entry.name}.zip"
        zip_path = os.path.join(rom_dir, zip_name)

        logger.debug(f"Checking ZIP: {zip_path}")

        if not os.path.isfile(zip_path):
            logger.debug(f"ZIP not found: {zip_path}")
            return None

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                # Cache namelist() result
                all_files = zip_file.namelist()
                logger.debug(f"ZIP contains {len(all_files)} files")

                for rom in dat_entry.roms:
                    if rom.name not in all_files:
                        logger.debug(f"ROM {rom.name} not in ZIP")
                        return None
                    zip_info = zip_file.getinfo(rom.name)
                    if rom.crc and zip_info.CRC != int(rom.crc, 16):
                        logger.debug(f"CRC mismatch for {rom.name}")
                        return None
                    elif rom.md5 and not rom.crc:
                        if md5:
                            import hashlib

                            md5_hash = hashlib.md5()
                            with zip_file.open(rom.name) as f:
                                for chunk in iter(lambda: f.read(4096), b""):
                                    md5_hash.update(chunk)
                            if md5_hash.hexdigest().lower() != rom.md5.lower():
                                logger.debug(f"MD5 mismatch for {rom.name}")
                                return None
                        else:
                            logger.debug(f"MD5 required for {rom.name}")
                            raise MD5ScanRequiredException(
                                f"MD5 scan required for {dat_entry.name}"
                            )

            logger.info(f"✓ Valid ZIP: {zip_path}")
            return zip_path

        except TimeoutError:
            logger.warning(f"⚠ TIMEOUT reading ZIP: {zip_path}")
            raise
        except (zipfile.BadZipFile, KeyError) as e:
            logger.error(f"Invalid ZIP file {zip_path}: {e}")
            return None

    def find_valid_zip_with_md5(self, dat_entry: "DATGameEntry") -> Optional[str]:
        """Find and validate zip file for a DAT entry with MD5 scanning"""
        zip_name = f"{dat_entry.name}.zip"
        rom_dir = dat_entry.dat.rom_path
        zip_path = os.path.join(rom_dir, zip_name)

        logger.debug(f"Checking ZIP with MD5: {zip_path}")

        if not os.path.isfile(zip_path):
            logger.debug(f"ZIP not found: {zip_path}")
            return None

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                # Cache namelist() result
                all_files = zip_file.namelist()
                logger.debug(f"ZIP contains {len(all_files)} files")

                for rom in dat_entry.roms:
                    if rom.name not in all_files:
                        logger.debug(f"ROM {rom.name} not in ZIP")
                        return None
                    zip_info = zip_file.getinfo(rom.name)
                    if rom.crc and zip_info.CRC != int(rom.crc, 16):
                        logger.debug(f"CRC mismatch for {rom.name}")
                        return None
                    elif rom.md5:
                        import hashlib

                        md5_hash = hashlib.md5()
                        with zip_file.open(rom.name) as f:
                            for chunk in iter(lambda: f.read(4096), b""):
                                md5_hash.update(chunk)
                        if md5_hash.hexdigest().lower() != rom.md5.lower():
                            logger.debug(f"MD5 mismatch for {rom.name}")
                            return None

            logger.info(f"✓ Valid ZIP (with MD5): {zip_path}")
            return zip_path

        except (zipfile.BadZipFile, KeyError) as e:
            logger.error(f"Invalid ZIP file {zip_path}: {e}")
            return None

    def extract_to_tempdir(self, zip_path: str) -> Optional[str]:
        """Extract zip to temp directory"""
        logger.debug(f"Extracting ZIP to temp: {zip_path}")

        try:
            self.temp_dir = tempfile.mkdtemp(dir=self.tmpdsk)
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                file_count = 0
                for file_info in zip_file.infolist():
                    if not file_info.filename.startswith("__MACOSX/"):
                        zip_file.extract(file_info, self.temp_dir)
                        file_count += 1
                logger.debug(f"Extracted {file_count} files")
            return Path(self.temp_dir)
        except Exception as e:
            logger.error(f"Extraction error {zip_path}: {e}")
            self.cleanup_tempdir()
            return None

    def cleanup_tempdir(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            logger.debug(f"Cleaning up temp directory: {self.temp_dir}")
            shutil.rmtree(self.temp_dir)
