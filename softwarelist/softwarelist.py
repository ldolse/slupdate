from __future__ import annotations

from html import unescape
from lxml import etree
from softwarelist.software import Software
from softwarelist.part import Part
from softwarelist.comment import Comment

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from media_registry import MediaRegistry, CDMedia
    from dat import GameEntry


class SoftwareList:
    def __init__(self):
        self.name = ""
        self.description = ""
        self.software_items: list["Software"] = []
        self._xml_tree: Optional[etree.ElementTree] = None  # For future writes
        self._lxml_replacements: dict[
            str, str
        ] = {}  # lxml formatting quirks to preserve

        # lazy loaded properties
        self._entries_by_name = {}
        self._redump_url_parts = {}

    @staticmethod
    def _get_lxml_replacements(xml_file_path: str) -> dict[str, str]:
        """
        Capture lxml formatting quirks for later restoration.
        Finds cases that lxml changes and tracks original strings to restore later.

        Args:
            xml_file_path: Path to XML file to read

        Returns:
            Dict of {lxml_output: original_input}
        """
        import re

        entity_list = re.compile(r">[^<]+?(&quot;)[^<]+?<")
        try:
            with open(xml_file_path, "r", encoding="utf-8") as f:
                xml_string = f.read()
        except FileNotFoundError:
            print(f"Error reading {xml_file_path}")
            return {}

        tag_regex = re.compile(r"<[^>]+? />")
        lxml_changes = {}
        for match in tag_regex.finditer(xml_string):
            tag_str = match.group(0)
            new_key = tag_str.replace(" />", "/>")
            lxml_changes[new_key] = tag_str
        for match in entity_list.finditer(xml_string):
            entity_str = match.group(0)
            new_key = unescape(entity_str)
            lxml_changes[new_key] = entity_str
        return lxml_changes

    @staticmethod
    def _restore_lxml_quirks(xml_output: bytes, replacements: dict[str, str]) -> str:
        """
        Restore lxml formatting quirks after etree.tostring().

        Args:
            xml_output: Output from etree.tostring() as bytes
            replacements: Dict of {lxml_output: original_input}

        Returns:
            Restored XML string with original formatting preserved
        """
        output = xml_output.decode("UTF-8")
        for lxml_output, original_input in replacements.items():
            output = output.replace(lxml_output, original_input)
        return output

    @classmethod
    def from_file(cls, xml_file: str) -> "SoftwareList":
        """
        Load a software list from an XML file.
        :param xml_file: Path to the XML file.
        :return: An instance of SoftwareList.
        """

        # Capture lxml formatting quirks BEFORE parsing
        lxml_replacements = cls._get_lxml_replacements(xml_file)

        def validate_parts(parts: list["Part"], basename: str = "cdrom") -> None:
            """
            Validate and automatically fix part names in a software item.

            Ensures parts are named sequentially as:
            - cdrom - single part entry
            - cdrom1, cdrom2, ... for multiple parts

            Supports custom basenames like 'dvdrom' or 'bdrom'.
            """

            if len(parts) == 1:
                # If there's only one part, ensure it's named correctly
                if parts[0].name != basename:
                    print(
                        f"⚠️  WARNING: {software.name} has invalid part name '{parts[0].name}'. Changed to '{basename}'"
                    )
                    parts[0].name = basename
            else:
                for idx, part in enumerate(parts):
                    # print(f"Validating part {idx}: {part.name}")
                    expected_name = f"{basename}{idx + 1}"
                    if part.name != expected_name:
                        print(
                            f"⚠️  WARNING: {software.name} has invalid part name '{part.name}'. Changed to '{expected_name}'"
                        )
                        part.name = expected_name

        def validate_software_names(items: list["Software"]) -> None:
            name_count = {}

            for idx, item in enumerate(items):
                if item.name in name_count:
                    new_name = f"{item.name}_{name_count[item.name]}"
                    print(
                        f"WARNING: Duplicate software name '{item.name}'. Renaming to '{new_name}' at position {idx}"
                    )
                    item.name = new_name
                else:
                    name_count[item.name] = 1

        parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
        tree = etree.parse(xml_file, parser)
        root = tree.getroot()

        instance = cls()
        instance.name = root.get("name", "")
        instance.description = root.get("description", "")

        platform = instance.name
        # Collect all <software> tags
        software_elements = [e for e in root if e.tag == "software"]

        for i, software_element in enumerate(software_elements):
            software = Software(platform=platform)
            software.name = software_element.get("name", "")
            software.cloneof = software_element.get("cloneof")
            software.supported = software_element.get("supported", "yes")

            # Collect comments directly before this <software>
            prev_sib = software_element.getprevious()
            while prev_sib is not None:
                if isinstance(prev_sib, etree._Comment):
                    comment_obj = Comment(prev_sib)
                    if (
                        "</software>" in comment_obj.text_content
                    ):  # stop if we find a commented out software element
                        break
                    if comment_obj not in software.comments:
                        software.comments.append(comment_obj)
                    # Move to the next previous sibling
                    prev_sib = prev_sib.getprevious()
                else:
                    break

            # Inline comments inside <software>
            for child in software_element:
                if isinstance(child, etree._Comment):
                    comment_obj = Comment(child)
                    if comment_obj not in software.comments:
                        software.comments.append(comment_obj)

            # Metadata
            description_elem = software_element.find("description")
            software.description = (
                (description_elem.text or "").strip()
                if description_elem is not None
                else ""
            )
            year_elem = software_element.find("year")
            software.year = (
                (year_elem.text or "").strip() if year_elem is not None else ""
            )
            publisher_elem = software_element.find("publisher")
            software.publisher = (
                (publisher_elem.text or "").strip()
                if publisher_elem is not None
                else ""
            )

            # Info tags
            for info in software_element.findall("info"):
                name = info.get("name", "").strip()
                value = info.get("value", "").strip()
                if name and value:
                    if name not in software.info_metadata:
                        software.info_metadata[name] = []
                    software.info_metadata[name].append(value)

                    # Auto-update MAME-supported attributes
                    for mame_tag in [
                        "alt_title",
                        "author",
                        "barcode",
                        "developer",
                        "distributor",
                        "install",
                        "isbn",
                        "oem",
                        "original_publisher",
                        "partno",
                        "pcb",
                        "programmer",
                        "release",
                        "serial",
                        "usage",
                        "version",
                    ]:
                        if name == mame_tag:
                            setattr(software, f"_{mame_tag}", value)

            # Parts
            part_base_name = "cdrom"
            disc_num = 0
            parts = []
            for part_element in software_element.findall("part"):
                disk_elem = None
                diskarea_elem = part_element.find("diskarea")
                if diskarea_elem is not None:
                    disk_elem = diskarea_elem.find("disk")

                part = Part(part_element=part_element, disk_element=disk_elem)
                part.name = part_element.get("name", "")
                part.part_of = software
                if part.name == part_base_name and disc_num == 0:
                    pass
                elif part.name == part_base_name:
                    part.name = f"{part_base_name}{disc_num}"
                    disc_num += 1
                part.interface = part_element.get("interface", "")

                # capture immediately preceding sibling comments
                prev_part_sib = part_element.getprevious()
                if isinstance(prev_part_sib, etree._Comment):
                    part.comments.append(Comment(prev_part_sib))

                # capture comments inside <part>
                for child in part_element:
                    if isinstance(child, etree._Comment):
                        comment_obj = Comment(child)
                        if comment_obj not in software.comments:
                            part.comments.append(comment_obj)

                parts.append(part)
            validate_parts(parts, "cdrom")
            software.parts = parts

            instance.software_items.append(software)
            validate_software_names(instance.software_items)

        # Cache the XML tree and lxml replacements for future writes
        instance._xml_tree = tree
        instance._lxml_replacements = lxml_replacements

        return instance

    @property
    def entries_by_name(self) -> dict[str, Software]:
        if not self._entries_by_name:
            for entry in self.software_items:
                self._entries_by_name[entry.name] = entry
        return self._entries_by_name

    @property
    def all_redump_url_parts(self) -> list[Part]:
        self._build_redump_url_parts()
        return (
            self._redump_url_parts["matched_url_parts"]
            + self._redump_url_parts["unmatched_url_parts"]
        )

    @property
    def unmatched_redump_url_parts(self) -> list[Part]:
        self._build_redump_url_parts()
        return self._redump_url_parts["unmatched_url_parts"]

    def _build_redump_url_parts(self):
        self._redump_url_parts = {"matched_url_parts": [], "unmatched_url_parts": []}
        matched = self._redump_url_parts["matched_url_parts"]
        unmatched = self._redump_url_parts["unmatched_url_parts"]
        for entry in self.software_items:
            for part in entry.parts:
                if part.redump_url:
                    if part.cdmedia:
                        matched.append(part)
                    else:
                        unmatched.append(part)

    def extract_source_data(self):
        """
        iterate through all software items and parse their comments.
        This is useful for extracting URLs or other data from comments.
        """
        # create a stub dat object for group reference
        from dat.rom_dat import RomDat

        dat = RomDat()
        dat.url = "http://mamedev.org/"
        for software in self.software_items:
            software.extract_rom_sources(dat)
            software.extract_redump_urls()

    def _register_entry(
        self,
        registry: MediaRegistry,
        game_entry: GameEntry,
        software_item: Software,
        part: Optional[Part] = None,
    ) -> None:
        registered: Optional[CDMedia] = None
        matched: bool = False
        if getattr(game_entry, "media", None) is None:
            registered, matched = registry.get_or_create_media(game_entry)
            if registered:
                game_entry.media = registered
                if matched and registered.dat_game_entry:
                    if (
                        part
                        and registered.dat_game_entry.dat.dat_group != "MAME-Comment"
                    ):
                        print(
                            f"✅ Matched existing media: {software_item.name} to {registered.dat_game_entry.name}"
                        )
                        registered.softlist_part = part
                        part.cdmedia = registered
                    else:
                        print(
                            f"⚠️  MAME comment for {software_item.name} matched against a duplicate soflist record: {registered.dat_game_entry.name}"
                        )
                elif not matched:
                    print(
                        f"🆕 No Match, created new media record for: {software_item.name}, hash {registered.sha1_signature}"
                    )
            elif registered == None:
                print(
                    f"❌ Could not register Software List media for: {game_entry.dat}: {game_entry.name}"
                )

    def register_to_media_registry(self, registry: MediaRegistry):
        """Register all GameEntries from Software/Parts to MediaRegistry and map them to correct Parts."""
        for software_item in self.software_items:
            # First pass: Register all GameEntries at root level (Software)
            for game_entry in software_item.game_entries:
                self._register_entry(registry, game_entry, software_item)
            # Second pass: Register all GameEntries from Parts
            for part in software_item.parts:
                if part.game_entry:
                    self._register_entry(registry, part.game_entry, software_item, part)

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "software_items": [s.to_dict() for s in self.software_items],
        }

    def write_to_file(self, xml_file_path: str) -> None:
        """
        Write current SoftwareList state back to XML file.
        Preserves existing XML structure, comments, and formatting.

        Args:
            xml_file_path: Path to XML file to write

        Raises:
            ValueError: If no XML tree is available for writing
        """
        if self._xml_tree is None:
            raise ValueError(
                "No XML tree available for writing. "
                "SoftwareList must be loaded from file first."
            )

        output = etree.tostring(
            self._xml_tree,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
            doctype='<!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">',
        ).decode("UTF-8")

        # Restore lxml formatting quirks if we captured them during load
        if hasattr(self, "_lxml_replacements") and self._lxml_replacements:
            output = self._restore_lxml_quirks(
                output.encode("UTF-8"), self._lxml_replacements
            )

        with open(xml_file_path, "w", encoding="utf-8") as f:
            f.write(output)

    def __repr__(self):
        return f"<SoftwareList '{self.name}' (Description: {self.description} | Entries: {len(self.software_items)})>"
