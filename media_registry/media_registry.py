import hashlib
from softwarelist import Software, Part
from typing import Dict, Optional, Tuple
from collections import OrderedDict
import os

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from dat import GameEntry as DATGameEntry

class CDMedia:
    def __init__(self, platform_key: str = None):
        self.id = None  # Will be set by MediaRegistry
        self.platform: str = platform_key

        # Core hash information
        self.sha1_signature: Optional[str] = ""
        self.crc_signature: Optional[str] = ""
        self.total_rom_size: int = 0
        self.confirmed_from_redump: bool = False

        # References to source objects that point to this media
        # self.dat_game_entry is the primary source reference
        self.dat_game_entry: Optional['DATGameEntry'] = None
        self._all_dat_references: Dict[str, 'DATGameEntry'] = {}  # {dat_name: entry}

        # Software list references
        self.softlist_title: Optional[Software] = None
        self.softlist_part: Optional['Part'] = None

        # Zip processing attributes
        self._zip_path: Optional[str] = None
        self._chd_path: Optional[str] = None
        self.processing_status: str = "pending"  # pending, processing, complete, failed

    @property
    def chd_path(self) -> Optional[str]:
        """Get the expected CHD path for this media"""
        if self._chd_path is None and self.dat_game_entry is not None and self.softlist_title is not None and self.platform is not None:
            # Generate CHD path based on dat entry and platform
            self._chd_path = os.path.join(
                self.platform,
                self.softlist_title.name,
                f"{self.dat_game_entry.name}.chd",)
        return self._chd_path

    @property
    def dat_entries(self) -> list["DATGameEntry"]:
        """Returns a dict of {group: [DATGameEntries]} for all groups."""
        result = {g: [] for g in ['redump', 'tosec', 'no-intro', 'other', 'MAME']}

        # Categorize entries by group from _all_dat_references
        for entry in self._all_dat_references.values():
            group = entry.dat.dat_group if hasattr(entry.dat, 'dat_group') else 'unknown'
            result[group].append(entry)

        return {g: v for g, v in result.items() if v}

    @property
    def matched(self) -> bool:
        """Check if this media is properly matched between DAT and softlist"""
        # Prevent recursion by checking if we're already in the matched property
        # Check if we have both a dat_game_entry with valid dat attribute
        # and a softlist_part reference
        if self.dat_game_entry is not None:
            dat_group = self.dat_game_entry.dat.dat_group
            if self.softlist_part is not None and dat_group != "MAME-Comment":
                return True
        return False

    def to_dict(self):
        return {
            "id": self.id,
            "matched": self.matched,
            "primary dat": self.dat_game_entry,
            "All Dats": self._all_dat_references,
            "sha1 sig": self.sha1_signature,
            "crc sig": self.crc_signature,
            "Softlist": self.softlist_title,
            "Soft Part": self.softlist_part
        }

    def add_dat_reference(self, game_entry: 'DATGameEntry'):
        """Track a DAT entry reference with priority handling"""
        if game_entry.dat.dat_group == 'redump':
            self.confirmed_from_redump = True
            self.dat_game_entry = game_entry
        elif self.dat_game_entry == None:
            self.dat_game_entry = game_entry
        # add to all references
        self._all_dat_references.update({game_entry.dat: game_entry})

    def add_softlist_reference(self, softlist_game: Software):
        """Track which Softlist games reference this media"""
        self.softlist_title = softlist_game

    def add_part_reference(self, part_obj: Part):
        """Track which parts reference this media"""
        self.softlist_part = part_obj

class MediaRegistry:
    def __init__(self, platform_key: Optional[str] = None):

        # Maps hash signatures to CDMedia objects
        self.media_hashes: Dict[str, CDMedia] = {}
        self.media_id_counter = 0
        self.media_directory: OrderedDict[CDMedia, None] = OrderedDict()
        self.platform_key = platform_key

    def get_or_create_media(self, game_entry: 'DATGameEntry') -> Tuple[CDMedia, bool]:
        """Get or create media for a DAT GameEntry

        Returns:
            Tuple[CDMedia, bool]: The media object and a boolean indicating if it was newly created
        """
        sha1_sig, crc_sig, size = self._calculate_hashes(game_entry)

        # Early exit for invalid signatures
        if not (sha1_sig or crc_sig):
            print(f"⚠️ No valid signature found for {game_entry.dat}: {game_entry.name}")
            return None, False

        # Step 1: Find existing media using any available hash
        matched_cdm = None
        for sig in [s for s in (sha1_sig, crc_sig) if s]:
            if sig not in self.media_hashes:
                continue
            # Prioritize SHA1 first
            if sig[1] == 'SHA1' and sig in self.media_hashes:
                matched_cdm = self.media_hashes[sig]

            elif sig[1] == 'CRC_SHA1' and sig in self.media_hashes:
                existing_media = self.media_hashes[sig]
                if matched_cdm is None:  # First match (only CRC available)
                    if existing_media.total_rom_size == size:
                        print(f"Info: CRC only match {game_entry.dat}: {game_entry.name}")
                        matched_cdm = existing_media
                    else:
                        print(f"⚠️ Size mismatch for CRC-only match - {game_entry.dat}: {game_entry.name}")
                        return None, False
                elif matched_cdm is not None and matched_cdm != existing_media:  # Potential collision!
                    if matched_cdm.total_rom_size == existing_media.total_rom_size:
                        print(f"⚠️ Possible duplicate media via CRC + SHA1 hash types for {game_entry.dat}: {game_entry.name}")
                        print(f"   Matched record: {matched_cdm.dat_game_entry.dat}: {matched_cdm.dat_game_entry.name}")
                        return None, False

        # Step 2: If existing media found, update it with all available hashes
        if matched_cdm:
            # Ensure all new signatures point to this CDMedia instance
            for sig in [sig for sig in (sha1_sig, crc_sig) if sig]:
                if sig not in self.media_hashes or self.media_hashes[sig] != matched_cdm:
                    self.media_hashes[sig] = matched_cdm
            # Add the current game entry as a reference
            matched_cdm.add_dat_reference(game_entry)
            return matched_cdm, True

        # Step 3: Create new media and register all hashes
        if matched_cdm == None:
            cd_media = self._create_media(sha1_sig, crc_sig, size)
            for sig in [sig for sig in (sha1_sig, crc_sig) if sig]:
                if sig not in self.media_hashes:
                    self.media_hashes[sig] = cd_media
                    self.media_hashes[sig].add_dat_reference(game_entry)
            self.media_directory[cd_media] = None
            return cd_media, False



    def _create_media(self, sha1_sig: str, crc_sig: str, size: int) -> CDMedia:
        """Create a new media entry with the given signature"""
        new_media = CDMedia(self.platform_key)
        new_media.sha1_signature = sha1_sig
        new_media.crc_signature = crc_sig
        new_media.total_rom_size = size
        self._assign_new_id(new_media)

        return new_media


    def _assign_new_id(self, media: CDMedia):
        """Assign a unique ID to this media"""
        self.media_id_counter += 1
        media.id = f"{self.media_id_counter:08d}"

    def _calculate_hashes(self, game_entry: 'DATGameEntry') -> Tuple[Tuple, Tuple, int]:
        """Generate hash signatures using the exact algorithm from original code"""
        if not game_entry.roms:
            return "", None, 0

        total_size = 0
        sha1_builder = hashlib.sha1()
        crc_builder = hashlib.sha1()

        rom_count = 0
        has_sha1 = False
        has_crc = False

        for rom in game_entry.roms:
            file_name = rom.name.lower()

            # Skip TOC files and special cases as per original algorithm
            if file_name.endswith(('.cue', '.gdi')) or file_name == 'ip.bin':
                continue

            # Track size for validation
            try:
                total_size += int(rom.size)
            except (ValueError, TypeError):
                print(f"⚠️   Invalid or missing 'size' attribute in ROM '{rom.name}'. Defaulting to 0.")
                total_size += 0
                pass

            rom_count += 1

            # Build SHA1 signature from ROMs with SHA1 hashes
            if rom.sha1:
                has_sha1 = True
                sha1_builder.update(rom.sha1.encode('utf-8'))

            # Build CRC signature for older DAT files (fallback)
            if rom.crc and rom.size:  # Only include if we have both values
                has_crc = True
                crc_key = f"crc:{rom.crc}~size:{rom.size}"
                crc_builder.update(crc_key.encode('utf-8'))

        sha1_signature = (sha1_builder.hexdigest(), 'SHA1') if has_sha1 else None
        crc_signature = (crc_builder.hexdigest(), 'CRC_SHA1') if has_crc and rom_count > 0 else None
        return sha1_signature, crc_signature, total_size

    def to_dict(self):
        return {
            "total_media": len(self.media_hashes),
            # print out the media id with a to_dict for each value in the directory

            "media": [m.to_dict() for m in self.media_hashes.values()],
            "more": {mid: media.to_dict() for mid, media in self.media_hashes.items()}
        }
