import re
from softwarelist.part import Part
from softwarelist.comment import Comment
from dat.rom_dat import GameEntry

class Software:
    def __init__(self, platform: str = "") -> None:
        # Standard attributes
        self.name = ""
        self.cloneof = None
        self.supported = "no"
        self.comments: list[Comment] = []
        self.description = ""
        self.year = ""
        self.publisher = ""
        self.parts: list[Part] = []
        self.redump_urls: list[str] = []
        self.game_entries: list[GameEntry] = []

        # Platform context for serial parsing
        self.platform = platform

        # Info metadata dictionary (raw key-value store)
        self.info_metadata: dict[str, list[str]] = {}

        # MAME-supported info tags with defaults as protected attributes
        mame_info_tags = [
            "alt_title", "author", "barcode", "developer", "distributor",
            "install", "isbn", "oem", "original_publisher", "partno",
            "pcb", "programmer", "release", "serial", "usage", "version"
        ]

        for tag in mame_info_tags:
            setattr(self, f"_{tag}", "")

    @property
    def all_comments(self) -> list[Comment]:
            """Returns a flat list of Comment objects including both software and part comments."""
            all_comments = self.comments.copy()
            for part in self.parts:
                all_comments.extend(part.comments)
            return all_comments

    @property
    def serial(self) -> list[str]:
        """Processes raw serial string into a clean, normalized list of serial numbers"""
        return self._process_serial(self._serial)

    def extract_rom_sources(self) -> None:
        """Parse comments into structured data."""
        # create a stub dat object for group reference
        from dat.rom_dat import RomDat
        dat = RomDat()
        dat.url = 'http://mamedev.org/'
        for comment in self.comments:
            self.game_entries.extend(comment.parse_rom_entries(self.name, dat))
        for part in self.parts:
            part.extract_rom_sources(dat)

        # shift any parsed items from the software entry to the individual parts
        self._map_items_to_parts(self.game_entries, 'game_entry')

    def extract_redump_urls(self) -> None:
        """Extract redump URLs from comments."""
        for comment in self.comments:
            if comment.redump_urls:
                self.redump_urls.extend(comment.redump_urls)
        for part in self.parts:
            part.extract_redump_url()

        # shift any parsed items from the software entry to the individual parts
        self._map_items_to_parts(self.redump_urls, 'redump_url')

    def _process_serial(self, raw_serial: str) -> list[str]:
        """
        Parse and expand platform-specific serial formats.

        Handles:
        - PSX-style ranges like "SLUS-013~SLUS-017"
        - Bracketed comments to be removed
        - Space/hyphen normalization
        """

        # Normalize input
        if not raw_serial.strip():
            return []

        platform = self.platform.lower()
        serials = []


        def expand_range(serial_range: str) -> list[str]:
            start, end = serial_range.split("~")
            prefix_match = re.match(r"([A-Za-z-]+)(\d+)", start)
            if not prefix_match:
                return [serial_range]  # Return original on failure

            prefix, num_str_start = prefix_match.groups()
            num_len = len(num_str_start)  # Preserve length with leading zeros
            num_start = int(num_str_start)

            end_match = re.match(rf"{prefix}(\d+)", end)
            if not end_match:
                return [serial_range]

            num_end = int(end_match.group(1))

            return [
                f"{prefix}{num:0{num_len}d}"  # Format with original length
                for num in range(num_start, num_end + 1)
            ]

        # Apply platform-specific rules
        if raw_serial:

            _bracket_c_platforms = {"psx", "dc"}  # Platforms where bracketed serials should be stripped
            # Remove bracketed comments
            if platform in _bracket_c_platforms:
                raw_serial = re.sub(r"$[^)]+$", "", raw_serial)

            if platform == "psx":
                # Normalize space -> hyphen for PSX serials like SLUS-01300 vs. SLUS 01300
                raw_serial = re.sub(r"([A-Z]{4})\s(\d{5})", r"\1-\2", raw_serial)

            # Split and process each part
            for item in [x.strip() for x in raw_serial.replace(" ", ",").split(",")]:
                if not item:
                    continue

                if platform == "psx":
                    range_match = re.match(r"(\d+)~([A-Z]+)", item)
                    if range_match or "~" in item and re.search(r"[A-Za-z]", item):
                        try:
                            serials.extend(expand_range(item))
                            continue
                        except Exception as e:
                            print(f"⚠️  Error expanding serial {item}: {e}")

                serials.append(item)

        return list(filter(None, serials))  # Remove empty strings

    def _map_games_to_parts(self):
        '''relocate games from software object to the correct parts based on comment order'''
        # Filter out "nodump" parts and get valid part list
        valid_parts = [part for part in self.parts if part.disk_status != "nodump"]
        part_count = len(valid_parts)
        game_count = len(self.game_entries)

        # Case 1: One-to-one mapping between valid Parts and GameEntries
        if part_count == 1 and game_count == 1:
            self._map_game_to_part(self.game_entries[0])

        # Case 2: Multiple valid Parts, same number of GameEntries → map in order
        elif part_count > 1 and len(valid_parts) == game_count:
            for i, game_entry in enumerate(self.game_entries.copy()):
                valid_parts[i].game_entry.append(game_entry)
                self.game_entries.remove(game_entry)

        # Case 3: Mismatch between number of GameEntries and valid Parts
        elif part_count != game_count and game_count >= 1:
            print(f'[Warning] - Different number of source references and software parts for {self.name}.')

    def _map_items_to_parts(self, source_list, target_attr):
        """Map items (GameEntry or redump URL) to valid Parts based on order.

        Invalid Parts are filtered out if they have disk_status == 'nodump'.
        """
        # Filter valid parts by excluding "nodump"
        valid_parts = [part for part in self.parts if part.disk_status != "nodump"]

        source_count = len(source_list)
        part_count = len(valid_parts)

        if not valid_parts:
            return  # No valid Parts to map

        # One-to-one mapping
        if part_count == 1 and source_count == 1:
            setattr(valid_parts[0], target_attr, source_list.pop(0))

        # Multiple parts and matching items count
        elif part_count > 1 and part_count == source_count:
            for i in range(part_count):
                setattr(valid_parts[i], target_attr, source_list[i])

            # Clear the entire list after mapping
            del source_list[:]

        # Mismatch: warn if mismatched
        elif source_count >= 1:
            print(f'⚠️ [Warning] - Mismatched {target_attr} mapping for "{self.name}":')
            print(f'               Valid parts: {part_count} | Items to map: {source_count}')


    def _map_game_to_part(self, game_entry):
        """Map a GameEntry to its correct Part based on DAT disc numbering."""
        dest_part = None

        # move single part items directly
        if len(self.parts) == 1:
            dest_part = self.parts[0]

        else: # multi-part logic
            dat_disc_name = game_entry.roms[0].name
            part_matches = self._find_part_by_disc_name(dat_disc_name)

            if part_matches:
                dest_part = part_matches[0]

        if dest_part is not None:
            dest_part.game_entry.append(game_entry)
            self.game_entries.remove(game_entry)

    def _find_part_by_disc_name(self, disc_name: str) -> list[Part]:
        """Find Parts matching a DAT's disc name (e.g., "Disc 1" → "cdrom1")."""
        # Logic example for common disc-to-part naming patterns
        part_mapping = {
            r"disc (\d+)": lambda x: f"cdrom{x.group(1)}",
        }

        matching_parts = []
        for pattern, formatter in part_mapping.items():
            match = re.search(pattern, disc_name.lower())
            if not match:
                continue

            target_name = formatter(match)
            for part in self.parts:
                if part.name == target_name:
                    matching_parts.append(part)
        if not matching_parts:
            print(f'[Debug]: failed to match part for {self.name}, dat_disc_name is {disc_name}')
        return matching_parts

    def to_dict(self):
        return {
            "name": self.name,
            "cloneof": self.cloneof,
            "supported": self.supported,
            "comments": self.comments,
            "description": self.description,
            "year": self.year,
            "publisher": self.publisher,
            "info_metadata": self.info_metadata,
            "parts": [p.to_dict() for p in self.parts],
            "redump_urls": self.redump_urls,
            "game_entries": self.game_entries,
        }

    def __repr__(self):
        return f"<Software '{self.name}' (Description: {self.description} | Parts: {len(self.parts)})>"