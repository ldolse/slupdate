from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class PlatformState:
    """Encapsulates all saveable state for a platform"""
    # Core configuration
    dat_directories: List[str] = field(default_factory=list)

    # Processing state
    _chd_build_index: int = 0
    matched_media_sigs: List[str] = field(default_factory=list)  # SHA1 or CRC signatures
    _chd_handling_preference: Optional[str] = None

    # CHD tracking - storing paths is more reliable than serializing objects
    validated_chds_paths: List[str] = field(default_factory=list)

    # Redump DB - this is already serializable in current implementation
    redump_db: Optional[Dict[str, Any]] = None

    # Directory availability tracking
    directory_status: Dict[str, str] = field(default_factory=dict)  # {path: "available" | "unavailable"}

    def mark_directory_status(self, path: str, status: str):
        """Mark a directory as available or unavailable"""
        self.directory_status[path] = status

    def is_directory_available(self, path: str) -> bool:
        """Check if a directory is marked as available"""
        return self.directory_status.get(path, "available") == "available"

    def add_validated_chd_path(self, chd_path: str):
        """Add a CHD path to the validated list"""
        if chd_path not in self.validated_chds_paths:
            self.validated_chds_paths.append(chd_path)

    def remove_validated_chd_path(self, chd_path: str):
        """Remove a CHD path from the validated list"""
        if chd_path in self.validated_chds_paths:
            self.validated_chds_paths.remove(chd_path)
