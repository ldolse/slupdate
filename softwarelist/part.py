from softwarelist.comment import Comment

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from softwarelist import Software
    from dat import GameEntry
    from media_registry import CDMedia

class Part:
    def __init__(self):
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

    def extract_rom_sources(self, dat) -> None:
        """Parse comments into structured data."""
        game_discs = []
        for comment in self.comments:
            game_discs.extend(comment.parse_rom_entries(self.part_of.name, dat))
        if len(game_discs) > 1:
            (f'⚠️ [Warning] - Too many source references for {self.part_of.name}, part "{self.name}" using first source')
        if game_discs:
            self.game_entry = game_discs[0]

    def extract_redump_url(self) -> None:
        """Extract redump URLs from comments."""
        redump_urls = []
        for comment in self.comments:
            if comment.redump_urls:
                redump_urls.extend(comment.redump_urls)
        if len(redump_urls) > 1:
            (f'⚠️ [Warning] - Too many source URL references for {self.part_of.name}, part "{self.name}" using first URL')
        if redump_urls:
            self.redump_url = redump_urls[0]

    def to_dict(self):
        return {
            "name": self.name,
            "Software": self.part_of.name,
            "interface": self.interface,
            #"comments": [c.to_dict() for c in self.comments],
            "comments": self.comments,
            "disk_name": self.disk_name,
            "disk_sha1": self.disk_sha1,
            "disk_status": self.disk_status,
            "redump_url": self.redump_url,
            "game_entry": self.game_entry if self.cdmedia else None,
            "cdmedia": self.cdmedia.to_dict() if self.cdmedia else None
        }
