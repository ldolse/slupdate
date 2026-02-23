from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from rom_management.processing.models import CHDExistingPreference


@dataclass
class PlatformState:
    """Encapsulates all saveable state for a platform"""

    # Core configuration
    dat_directories: List[str] = field(default_factory=list)

    # Processing state
    _chd_build_index: int = 0
    matched_media_sigs: List[str] = field(
        default_factory=list
    )  # SHA1 or CRC signatures
    _chd_handling_preference: CHDExistingPreference = CHDExistingPreference.ASK

    # Validated ZIP paths: {signature: zip_path}
    # This persists the ZIP path found during validation so CHD build can find it later
    validated_zip_paths: Dict[str, str] = field(default_factory=dict)

    # CHD tracking - storing paths is more reliable than serializing objects
    validated_chds_paths: List[str] = field(default_factory=list)

    # Redump DB - this is already serializable in current implementation
    redump_db: Optional[Dict[str, Any]] = None

    def add_validated_chd_path(self, chd_path: str):
        """Add a CHD path to the validated list"""
        if chd_path not in self.validated_chds_paths:
            self.validated_chds_paths.append(chd_path)

    def remove_validated_chd_path(self, chd_path: str):
        """Remove a CHD path from the validated list"""
        if chd_path in self.validated_chds_paths:
            self.validated_chds_paths.remove(chd_path)

    def add_validated_zip_path(self, media_sig: str, zip_path: str):
        """Store the ZIP path for a validated media signature"""
        self.validated_zip_paths[media_sig] = zip_path
        if media_sig not in self.matched_media_sigs:
            self.matched_media_sigs.append(media_sig)

    def get_zip_path(self, media_sig: str) -> Optional[str]:
        """Get the stored ZIP path for a media signature"""
        return self.validated_zip_paths.get(media_sig)

    def is_validated(self, media_sig: str) -> bool:
        """Check if a media signature has been validated"""
        return media_sig in self.matched_media_sigs
