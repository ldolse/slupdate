from lxml import etree
from softwarelist.comment import Comment

from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from softwarelist import Software
    from dat import GameEntry, RomDat
    from media_registry import CDMedia


class Part:
    def __init__(
        self,
        part_element: Optional[etree.Element] = None,
        disk_element: Optional[etree.Element] = None,
    ):
        self.name = ""
        self.part_of: Software = None
        self.interface = ""
        self.comments: list[Comment] = []
        self.disk_name: str = ""
        self.disk_sha1: str = ""
        self.disk_status: str = ""  # mame software disk status
        self.cdmedia: CDMedia = None # CdMedia object from MediaRegistry
        self.redump_url: str = ""
        self.game_entry: GameEntry = None

        self._part_element: Optional[etree.Element] = part_element
        self._disk_element: Optional[etree.Element] = disk_element

        if disk_element is not None:
            self.disk_name = disk_element.get("name", "").strip()
            self.disk_sha1 = disk_element.get("sha1", "").strip()
            self.disk_status = disk_element.get("status", "").strip()

        if part_element is not None:
            self.name = part_element.get("name", "")
            self.interface = part_element.get("interface", "")

    @property
    def matched(self) -> bool:
        """Returns True if part has a DAT match"""
        if (
            self.cdmedia is not None
            and self.cdmedia.dat_game_entry.dat.dat_group != "MAME-Comment"
        ):
            return True
        return False

    @property
    def source_group(self) -> Optional[str]:
        """Returns the source group from the associated GameEntry if it exists, otherwise None."""
        if hasattr(self, "cdmedia") and self.cdmedia is not None:
            if (
                hasattr(self.cdmedia, "softlist_part")
                and self.cdmedia.softlist_part is not None
                and hasattr(self.cdmedia, "dat_game_entry")
                and self.cdmedia.dat_game_entry is not None
            ):
                return self.cdmedia.dat_game_entry.dat_group
        return None

    @property
    def part_element(self) -> etree.Element:
        """Returns the XML element for this part (for direct manipulation)"""
        if self._part_element is None:
            raise ValueError("Part has no XML element reference")
        return self._part_element

    @property
    def disk_element(self) -> etree.Element:
        """Returns the XML disk element for this part (for direct manipulation)"""
        if self._disk_element is None:
            raise ValueError("Part has no disk XML element reference")
        return self._disk_element

    def update_chd_metadata(
        self,
        new_sha1: Optional[str] = None,
        new_filename: Optional[str] = None,
        source_group: Optional[str] = None,
    ) -> None:
        """
        Update disk SHA1 hash, filename, and remove bad dump status.

        Args:
            new_sha1: New CHD hash (or None to skip hash update)
            new_filename: New filename from DAT (or None to skip filename update)
            source_group: Source group (redump/TOSEC/no-intro) for status removal

        Raises:
            ValueError: If no disk element exists for this part
        """
        if self._disk_element is None:
            raise ValueError("Part has no disk element to update")

        disk_element = self._disk_element

        if new_sha1:
            self.disk_sha1 = new_sha1
            disk_element.set("sha1", new_sha1)

        if new_filename:
            self.disk_name = new_filename
            disk_element.set("name", new_filename)

        if source_group and source_group.lower() in ["redump", "tosec"]:
            current_status = disk_element.get("status")
            if current_status in ["nodump", "baddump"]:
                del disk_element.attrib["status"]
                self.disk_status = ""

    def extract_rom_sources(self, dat: "RomDat") -> None:
        """Parse comments into structured data."""
        game_discs = []
        for comment in self.comments:
            game_discs.extend(comment.parse_rom_entries(self.part_of.name, dat))
        if len(game_discs) > 1:
            (
                f'⚠️ [Warning] - Too many source references for {self.part_of.name}, part "{self.name}" using first source'
            )
        if game_discs:
            self.game_entry = game_discs[0]

    def extract_redump_url(self) -> None:
        """Extract redump URLs from comments."""
        redump_urls = []
        for comment in self.comments:
            if comment.redump_urls:
                redump_urls.extend(comment.redump_urls)
        if len(redump_urls) > 1:
            (
                f'⚠️ [Warning] - Too many source URL references for {self.part_of.name}, part "{self.name}" using first URL'
            )
        if redump_urls:
            self.redump_url = redump_urls[0]

    def to_dict(self):
        return {
            "name": self.name,
            "Software": self.part_of.name,
            "interface": self.interface,
            # "comments": [c.to_dict() for c in self.comments],
            "comments": self.comments,
            "disk_name": self.disk_name,
            "disk_sha1": self.disk_sha1,
            "disk_status": self.disk_status,
            "redump_url": self.redump_url,
            "game_entry": self.game_entry if self.cdmedia else None,
            "cdmedia": self.cdmedia.to_dict() if self.cdmedia else None,
        }
