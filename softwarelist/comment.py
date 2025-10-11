from lxml import etree
import re

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from dat.rom_dat import GameEntry


class Comment:
    def __init__(self, element: etree._Element):
        self.element = element          # Reference to XML node (lxml.etree._Comment)
        self.text_content = element.text if isinstance(element, etree._Comment) else ""
        self.toc_pattern = re.compile(r'\.cue|\.gdi', re.IGNORECASE)

    @property
    def is_before_element(self) -> bool:
        """Determines whether this comment precedes another element."""
        next_sib = self.element.getnext()
        return (
            isinstance(next_sib, (etree._ElementTree, etree._Element))
            and next_sib.tag != "#comment"
        )

    @property
    def rom_lines(self) -> list[str]:
        """Extract all <rom> block lines from this comment."""
        return [line.strip() for line in self.text_content.split('\n')
                if re.match(r'^\s*<rom\s+name="', line, re.IGNORECASE)]

    @property
    def redump_urls(self) -> list[str]:
        """Extract all http://redump.org/disc/... URLs from this comment."""
        return re.findall(
            r'https?://(?:www\.)?redump\.org/disc/\d{2,6}/?',
            self.text_content,
            re.IGNORECASE
        )

    @property
    def is_inside_element(self) -> bool:
        """Determines whether this comment is a child of an element."""
        parent = self.element.getparent()
        return isinstance(parent, etree._Element)

    def set_text(self, new_text: str):
        """Update the text content in memory and XML tree"""
        self.text_content = new_text
        if hasattr(self.element, "text"):
            self.element.text = new_text

    def delete_from_tree(self) -> None:
        """Remove this comment from the XML tree."""
        parent = self.element.getparent()
        if parent is not None:
            parent.remove(self.element)

    def insert_before_element(self, target_element: etree._Element):
        """Insert this comment before a specific element in the XML tree."""
        parent = target_element.getparent()
        if parent is not None and self.element in parent:
            idx = list(parent).index(target_element)
            parent.insert(idx, self.element)

    def __str__(self) -> str:
        return f"Comment(text='{self.text_content}', position={self._get_position()})"

    def _get_position(self):
        """Helper to describe where the comment appears in XML structure."""
        if self.is_inside_element:
            return "inside"
        elif self.is_before_element:
            return "before"
        else:
            return "standalone"

    def to_dict(self) -> dict:
        """Convert the comment to a dictionary representation."""
        return {
            "text": self.text_content,
            "position": self.element,
        }

    def _split_data_by_discs(self):
        '''
        Splits a comment string into separate disc groups based on presence of toc files.

        Returns:
            List[str] - Each element represents one disc's worth of ROM data.
        '''
        discs = []
        current_disc = ''
        toc_first = False
        for i, line in enumerate(self.rom_lines):
            toc = False
            if self.toc_pattern.search(line):
                toc = True
            if toc and i == 0:
                toc_first = True
                current_disc += line.strip()
                # skip any further logic for this case
                continue
            # if it's a new TOC file append the current disc and start a new one
            if toc_first and toc:
                discs.append(current_disc)
                current_disc = line.strip()
            # in this case add the toc to the current disc and start a new one
            elif not toc_first and toc:
                current_disc += line.strip()
                discs.append(current_disc)
                current_disc = ''
            # keep adding tracks to the current disc otherwise
            else:
                current_disc += line.strip()
        # add the last disc to the disc list
        if current_disc not in discs:
            discs.append(current_disc)
        return discs


    def parse_rom_entries(self, name: str, dat) -> list['GameEntry']:
        """Parse all <rom> entries from this comment into GameEntry objects."""
        game_discs = []
        if not self.rom_lines:
            return game_discs

        if sum(len(self.toc_pattern.findall(line)) for line in self.rom_lines) > 1:
            # Multiple discs entries found
            discs = self._split_data_by_discs()
            for disc in discs:
                game_discs.append(self._xml_to_game_entries(disc, name, dat))
        else:
            # Single disc entry found
            game_discs.append(self._xml_to_game_entries('\n'.join(self.rom_lines), name, dat))

        return game_discs


    def _xml_to_game_entries(self, game_lines, name, dat) -> 'GameEntry':
        from dat.rom_dat import GameEntry, Rom
        # Wrap in minimal XML structure for parsing
        escaped_comment = re.sub(r'&','&amp;',game_lines)
        xml_str = f"<datafile><game name='{name}'>\n{escaped_comment}\n</game></datafile>"
        try:
            root = etree.fromstring(xml_str)
            dat_name = 'Software List'
            dat_group = 'MAME'

            for game_elem in root.findall('.//game'):
                name = game_elem.get('name', '').strip()
                category = game_elem.findtext('category', default='')
                description = game_elem.findtext('description', default='')

                try:
                    size_attr = int(game_elem.get("size", "0"))
                except ValueError:
                    print(f"⚠️ Warning: Invalid or missing 'size' attribute in ROM '{name}'. Defaulting to 0.")
                    size_attr = 0

                roms = [
                    Rom(**{
                        'name': r.attrib['name'],
                        'size': size_attr,
                        'crc': r.attrib.get('crc', '').upper(),
                        'md5': r.attrib.get('md5', '').lower(),
                        'sha1': r.attrib.get('sha1', '').lower()
                    })
                    for r in game_elem.findall('rom')
                ]

                return GameEntry(name, category, description, roms, dat)

        except etree.XMLSyntaxError:
            print(f"⚠️  Invalid XML in comment: {xml_str}")
            return None

