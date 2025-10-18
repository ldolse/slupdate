from lxml import etree
import os

class LogiqxDAT:
    def __init__(self):
        # Define all expected header attributes with defaults
        for attr in ['name', 'description', 'category', 'version', 'date', 'author',
                    'email', 'homepage', 'url', 'comment']:
            setattr(self, f'_{attr}', '')
        self.clrmamepro = False
        # Header attributes will be set dynamically
        self.header = {}
        self.file_path = None
        self.rom_path = None # set by platform

    @classmethod
    def from_file(cls, file_path: str):
        parser = etree.XMLParser(no_network=True)
        tree = etree.parse(file_path, parser)
        root = tree.getroot()

        instance = cls()
        instance.file_path = file_path
        header_element = root.find('header')
        if header_element is not None:
            instance._parse_header(header_element)

        # Allow subclasses to parse their own content
        instance._custom_parse(root)  # This will be overridden in child classes

        return instance

    def _parse_header(self, header_element):
        """Standardized header parsing"""
        for child in header_element:
            self.header[child.tag] = child.text.strip()
            setattr(self, child.tag.lower(), child.text.strip())

    def _custom_parse(self, root_element):
        """Placeholder for custom parsing in subclasses"""
        pass

    @property
    def file_name(self) -> str:
        """Extract the file name from the file path."""
        return os.path.basename(self.file_path) if self.file_path else None

    @property
    def dat_group(self) -> str:
        """Determine the DAT group based on URL in header.

        Returns one of: 'redump', 'tosec', 'no-intro', 'other', or 'unknown'.
        """
        DAT_GROUPS = {
            'redump': ('redump.org',),
            'no-intro': ('no-intro.org',),
            'tosec': ('tosecdev.org',),
            'MAME-Comment': ('mamedev.org',),
            'mameredump': ('github.com/MetalSlug/MAMERedump',),
            'MAME-Slupdate': ('slupdate',),

        }

        try:
            url = self.header.get('url', '').lower()
            for group, patterns in DAT_GROUPS.items():
                if any(pattern in url for pattern in patterns):
                    return group
            return 'other'

        except Exception as e:
            print(f"DAT Group Detection Error: {e} for DAT '{self.file_path}'")
            return 'unknown'


