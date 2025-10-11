from dat.logiqx_dat import LogiqxDAT
from typing import Optional
from media_registry import MediaRegistry

class Rom:
    """Represents a ROM entry in a DAT file."""
    def __init__(self, name: str, size: int, crc: str, md5: str, sha1: str):
        self.name = name
        self.size = size
        self.crc = crc.upper()
        self.md5 = md5.lower()
        self.sha1 = sha1.lower()

    def to_dict(self):
        return {
            "name": self.name,
            "size": self.size,
            "crc": self.crc,
            "md5": self.md5,
            "sha1": self.sha1,
        }

    def __repr__(self):
        return f"<Rom '{self.name}'>"


class GameEntry:
    """Represents a game entry in a DAT file."""
    def __init__(self, name: str, category: str, description: str, roms=None, dat: "RomDat" = None):
        from media_registry import CDMedia
        self.name = name
        self.dat: RomDat = dat # Reference to parent DAT
        self.category = category
        self.description = description
        self.roms = roms if roms is not None else []
        self.media: Optional[CDMedia] = None

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "dat group": self.dat.dat_group,
            "rom path": self.dat.rom_path,
            "roms": [r.to_dict() for r in self.roms],
            "CDM_ID": self.media.to_dict()
        }

    def __repr__(self):
        return f"<Game '{self.name}' (Category: {self.category} | ROMs: {len(self.roms)})>"

class RomDat(LogiqxDAT):
    """Represents a Redump/TOSEC style DAT file containing Game & ROM entries."""
    def __init__(self):
        super().__init__()
        self.games = []

    def _parse_games(self, root_element):
        """Parse <game> elements with multiple <rom>s"""
        games = []
        for game_elem in root_element.findall('.//game'):
            name = game_elem.get('name', '').strip()


            category = game_elem.findtext('category', default=None)
            description = game_elem.findtext('description', default=None)

            roms = [Rom(**{
                'name': r.attrib['name'],
                'size': int(r.attrib['size']),
                'crc': r.attrib.get('crc', ''),
                'md5': r.attrib.get('md5', ''),
                'sha1': r.attrib.get('sha1', '')
            }) for r in game_elem.findall('rom')]

            games.append(GameEntry(name, category, description, roms, self))
        self.games = games

    # Override the placeholder method from base class
    def _custom_parse(self, root_element):
        self._parse_games(root_element)

    def register_to_media_registry(self, registry: MediaRegistry):
        for game_entry in self.games:
            registered, matched = registry.get_or_create_media(game_entry)

            if registered is not None:
                game_entry.media = registered  # Store reference to CDMedia

                if matched:
                    print(f"✅ Matched existing media: {game_entry.dat}: {game_entry.name}")
                else:
                    print(f"🆕 Created new media for: {game_entry.dat}: {game_entry.name}, hash:{registered.sha1_signature}")
            else:
                print(f"❌ Could not register media for: {game_entry.dat}: {game_entry.name}")

    def to_dict(self):
        return {
            "name": self.name,
            "dat group": self.dat_group,
            "games": [g.to_dict() for g in self.games],
        }

    def __repr__(self):
        return f"<DAT '{getattr(self, 'name', '')}' with {len(self.games)} games>"
