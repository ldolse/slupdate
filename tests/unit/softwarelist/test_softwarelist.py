import tempfile
import os
import pytest

from softwarelist.softwarelist import SoftwareList


class TestSoftwareListWrite:
    """Test SoftwareList write_to_file functionality"""

    def test_write_to_file_creates_xml(self):
        """Test that write_to_file creates valid XML output"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("""<?xml version="1.0"?>
<!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">
<softwarelist name="test" description="Test">
</softwarelist>""")
            test_file = f.name

        try:
            sl = SoftwareList.from_file(test_file)

            sl.write_to_file(test_file)

            with open(test_file, "r") as f:
                content = f.read()
                # lxml may use single quotes, accept either
                assert "<?xml version=" in content
                assert "<softwarelist" in content
                assert "test" in content

        finally:
            os.unlink(test_file)

    def test_write_to_file_preserves_content(self):
        """Test that write_to_file preserves content"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("""<?xml version="1.0"?>
<!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">
<softwarelist name="test" description="Test Description">
</softwarelist>""")
            test_file = f.name

        try:
            sl = SoftwareList.from_file(test_file)
            original_description = sl.description
            original_name = sl.name

            sl.write_to_file(test_file)

            with open(test_file, "r") as f:
                content = f.read()
                assert original_description in content
                assert original_name in content

        finally:
            os.unlink(test_file)

    def test_write_to_file_without_tree_raises_error(self):
        """Test that write_to_file raises error if no XML tree"""
        sl = SoftwareList()

        with pytest.raises(ValueError, match="No XML tree available"):
            sl.write_to_file("/some/path.xml")

    def test_write_to_file_preserves_lxml_quirks(self):
        """Test that write_to_file preserves lxml formatting quirks"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            # Write XML with lxml quirks (self-closing tag with space)
            f.write("""<?xml version="1.0"?>
<!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">
<softwarelist name="test" description="Test">
    <software name="test1">
        <description>Test</description>
        <part name="cdrom" interface="cdrom">
            <dataarea name="cdrom" size="777777">
                <disk name="disk1" sha1="abc123" />
            </dataarea>
        </part>
    </software>
</softwarelist>""")
            test_file = f.name

        try:
            sl = SoftwareList.from_file(test_file)

            sl.write_to_file(test_file)

            with open(test_file, "r") as f:
                content = f.read()
                # Check that self-closing tag with space is preserved
                assert 'sha1="abc123" />' in content

        finally:
            os.unlink(test_file)
