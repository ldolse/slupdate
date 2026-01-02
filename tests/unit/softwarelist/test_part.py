import pytest
from lxml import etree
from typing import Optional
from softwarelist.part import Part


class TestPartXmlElementAccess:
    """Test Part XML element references and updates"""

    def test_part_stores_element_references(self):
        """Part should store references to its XML elements"""
        part_elem = etree.Element("part", name="cdrom")
        diskarea_elem = etree.SubElement(part_elem, "diskarea")
        disk_elem = etree.SubElement(
            diskarea_elem, "disk", name="game.chd", sha1="abc123"
        )

        part = Part(part_element=part_elem, disk_element=disk_elem)

        assert part._part_element is part_elem
        assert part._disk_element is disk_elem
        assert part.part_element is part_elem
        assert part.disk_element is disk_elem

    def test_part_properties_raise_error_without_references(self):
        """Part properties should raise ValueError if no element references"""
        part = Part()

        with pytest.raises(ValueError, match="no XML element reference"):
            _ = part.part_element

        with pytest.raises(ValueError, match="no disk XML element reference"):
            _ = part.disk_element

    def test_update_chd_metadata_updates_hash(self):
        """update_chd_metadata should update SHA1 in memory and XML"""
        disk_elem = etree.Element("disk", name="old.chd", sha1="old_hash")
        part = Part(disk_element=disk_elem)

        part.update_chd_metadata(new_sha1="new_hash")

        assert part.disk_sha1 == "new_hash"
        assert disk_elem.get("sha1") == "new_hash"

    def test_update_chd_metadata_updates_filename(self):
        """update_chd_metadata should update filename in memory and XML"""
        disk_elem = etree.Element("disk", name="old.chd", sha1="abc123")
        part = Part(disk_element=disk_elem)

        part.update_chd_metadata(new_filename="new.chd")

        assert part.disk_name == "new.chd"
        assert disk_elem.get("name") == "new.chd"

    def test_update_chd_metadata_updates_both(self):
        """update_chd_metadata should update both hash and filename"""
        disk_elem = etree.Element("disk", name="old.chd", sha1="old_hash")
        part = Part(disk_element=disk_elem)

        part.update_chd_metadata(new_sha1="new_hash", new_filename="new.chd")

        assert part.disk_sha1 == "new_hash"
        assert part.disk_name == "new.chd"
        assert disk_elem.get("sha1") == "new_hash"
        assert disk_elem.get("name") == "new.chd"

    def test_update_chd_metadata_removes_nodump_status_redump(self):
        """update_chd_metadata should remove nodump for redump source"""
        disk_elem = etree.Element(
            "disk", name="game.chd", sha1="abc123", status="nodump"
        )
        part = Part(disk_element=disk_elem)

        part.update_chd_metadata(source_group="redump")

        assert "status" not in disk_elem.attrib
        assert part.disk_status == ""

    def test_update_chd_metadata_removes_baddump_status_tocsec(self):
        """update_chd_metadata should remove baddump for TOSEC source (case-insensitive)"""
        disk_elem = etree.Element(
            "disk", name="game.chd", sha1="abc123", status="baddump"
        )
        part = Part(disk_element=disk_elem)

        part.update_chd_metadata(source_group="TOSEC")

        assert "status" not in disk_elem.attrib
        assert part.disk_status == ""

    def test_update_chd_metadata_preserves_status_no_intro(self):
        """update_chd_metadata should NOT remove status for no-intro source"""
        disk_elem = etree.Element(
            "disk", name="game.chd", sha1="abc123", status="nodump"
        )
        part = Part(disk_element=disk_elem)

        part.update_chd_metadata(source_group="no-intro")

        assert disk_elem.get("status") == "nodump"
        assert part.disk_status == "nodump"

    def test_update_chd_metadata_no_source_group_skips_status(self):
        """update_chd_metadata should skip status removal if no source_group"""
        disk_elem = etree.Element(
            "disk", name="game.chd", sha1="abc123", status="nodump"
        )
        part = Part(disk_element=disk_elem)

        part.update_chd_metadata(new_sha1="new_hash")

        assert disk_elem.get("status") == "nodump"
        assert disk_elem.get("sha1") == "new_hash"

    def test_update_chd_metadata_raises_error_without_disk_element(self):
        """update_chd_metadata should raise ValueError if no disk element"""
        part = Part()

        with pytest.raises(ValueError, match="no disk element"):
            part.update_chd_metadata(new_sha1="abc")

    def test_part_without_elements_raises_property_errors(self):
        """Part created without element references should raise errors"""
        part = Part()

        with pytest.raises(ValueError, match="no XML element reference"):
            _ = part.part_element

        with pytest.raises(ValueError, match="no disk XML element reference"):
            _ = part.disk_element
