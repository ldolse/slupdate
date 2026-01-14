import os
import pathlib
import re
import subprocess
from media_registry import CDMedia

from typing import Optional, Dict


class CHDCreationException(Exception):
    def __init__(self, chd_path: str, error_message: str):
        self.chd_path = chd_path
        self.error_message = error_message
        super().__init__(f"Error creating CHD at {chd_path}: {error_message}")


class CHDAlreadyExistsException(Exception):
    """Exception raised when a CHD already exists during processing"""

    def __init__(
        self,
        chd_path: str,
        existing_version: Optional[str] = None,
    ):
        self.chd_path = chd_path
        self.existing_version = existing_version
        super().__init__(f"CHD already exists at {chd_path}")

class CHDNotFoundException(Exception):
    """Exception raised when a CHD file is not found"""

    def __init__(self, chd_path: str):
        self.chd_path = chd_path
        super().__init__(f"CHD file not found at {chd_path}")

class CHDInvalidException(Exception):
    """Exception raised when a CHD file is invalid"""

    def __init__(self, chd_path: str, error_message: str):
        self.chd_path = chd_path
        self.error_message = error_message
        super().__init__(f"Invalid CHD at {chd_path}: {error_message}")

class CHDSourceException(Exception):
    """Exception raised when there is an issue with the CHD source data"""

    def __init__(self, toc_source: str, error_message: str):
        self.toc_source = toc_source
        self.error_message = error_message
        super().__init__(f"Error with CHD source {toc_source}: {error_message}")


class CHD:
    """
    Represents a CHD (Compressed Hunks of Data) file as a Python object.

    This class provides functionality to create, read, and manipulate CHD files,
    with properties that are set either during creation or by parsing an existing CHD.
    """

    def __init__(
        self,
        chd_path=None,
        source: CDMedia = None,
        base_path=None,
        check_chdman: bool = False,
        toc_source: Optional[str] = None,
    ):
        """
        Initialize a CHD object.

        Args:
            chd_path (str): Path to an existing CHD file for reading
            output_path (str): Output path for the created CHD
        """
        # Properties set during initialization or by parsing existing CHD
        self.path = ""  # Path to the CHD file
        self.name = None  # Name of the CHD (without extension)
        self.extension = ".chd"  # File extension
        self.size = 0  # Size in bytes
        self.sha1 = None  # SHA1 hash
        self.parent_sha = None  # Parent CHD SHA1 if applicable
        self.logical_size = None  # Logical size of the original data
        self.compression = None  # Compression type used
        self.error = None  # Error message if any issues arise
        self.source: CDMedia = source  # Source DAT game entry if applicable
        self.toc_source = None  # TOC source, required for CD-based CHDs
        self._base_path = base_path  # Base path to create the softlist title directory
        self.output_path = (
            None  # Output path for CHD creation based on base_path and softlist title
        )
        self.preexisting = False  # Flag indicating if CHD already exists
        self.chdman_version = 280  # chdman version as integer (e.g., 280 for 0.280)

        if chd_path and os.path.exists(chd_path):
            # Initialize from existing CHD file
            self._initialize_from_existing(chd_path)
        elif source and toc_source and base_path:
            self.source = source
            self.toc_source = toc_source
            self.title = (
                self.source.softlist_part.part_of.name
                if self.source.softlist_part and self.source.softlist_part.part_of
                else None
            )
            if not self.title:
                raise ValueError("Source must have a softlist title for CHD creation")
            self.output_path = pathlib.Path(base_path) / self.title
            # Initialize for CHD creation
            self._initialize_for_creation()
        elif check_chdman:
            info = self._get_chd_info(check_chdman=True)
            if "chdman_version" not in info:
                raise EnvironmentError("chdman not found or not working")
        else:
            raise ValueError(
                "Either provide chd_path for reading or both toc source and output_path for creation"
            )

    def _initialize_from_existing(self, chd_path):
        """
        Initialize CHD object from an existing CHD file.

        Args:
            chd_path (str): Path to the existing CHD file
        """
        self.path = pathlib.Path(chd_path)
        if not self.path.exists():
            raise CHDNotFoundException(chd_path)
        self.name = self.path.stem
        self.size = os.path.getsize(chd_path)

        # Get CHD information
        info = self._get_chd_info()
        if info:
            self.sha1 = info.get("sha1")
            self.parent_sha = info.get("parent_sha")
            self.logical_size = info.get("logical_size")
            self.compression = info.get("compression")
        else:
            self.error = "Failed to retrieve CHD information"
            raise CHDInvalidException(chd_path, self.error)

    def _initialize_for_creation(self):
        """
        Initialize CHD object for creation.

        Args:
            output_path (str): Path where the CHD will be created
        """
        if not self._base_path:
            raise ValueError("Base path must be provided for CHD creation")
        self.output_path = pathlib.Path(self._base_path) / self.title
        self.name = self.source.dat_game_entry.name  # use DAT game name
        if not self.name:
            raise ValueError("Source must have a filename name for CHD creation")
        self.path = f"{self.output_path}/{self.name}.chd"

        self._create()

    @property
    def chdman_uptodate(self):
        version_string = self._get_chd_info(check_chdman=True).get(
            "chdman_version", "0.0"
        )
        v = list(map(int, version_string.split(".")))
        v_target = [0, self.chdman_version]
        return all(x >= y for x, y in zip(v, v_target))

    def _get_chd_info(self, check_chdman=False) -> Dict[str, str]:
        """
        Get comprehensive information about the CHD file using chdman.

        Returns:
            dict: Dictionary containing all CHD information from chdman output
        """
        if not os.path.exists(self.path) and not check_chdman:
            return {"error": "CHD file does not exist"}

        command = ["chdman"]
        if not check_chdman:
            command += ["info", "-i", str(self.path)]

        info = {}

        try:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE)
            output = proc.stdout.read().decode("ascii").split("\n")

            # Parse the chdman version line
            for line in output:
                if re.findall(
                    r"^chdman - MAME Compressed Hunks of Data \(CHD\) manager", line
                ):
                    # Extract version number
                    version_match = re.search(r"(\d+\.\d+)", line)
                    if version_match:
                        info["chdman_version"] = version_match.group(1)
                        break

            # Parse all other information lines
            for line in output:
                if re.findall(r"^SHA1:", line):
                    info["sha1"] = re.sub(r"\s*SHA1:\s*", "", line).strip()
                elif re.findall(r"^Parent SHA", line):
                    info["parent_sha"] = re.sub(r"\s*Parent SHA:\s*", "", line).strip()
                elif re.findall(r"^File Version:", line):
                    info["file_version"] = re.sub(
                        r"\s*File Version:\s*", "", line
                    ).strip()
                elif re.findall(r"^Logical size:", line):
                    info["logical_size"] = re.sub(
                        r"\s*Logical size:\s*", "", line
                    ).strip()
                elif re.findall(r"^Compression:", line):
                    info["compression"] = re.sub(
                        r"\s*Compression:\s*", "", line
                    ).strip()
                elif re.findall(r"^Hunk Size:", line):
                    info["hunk_size"] = re.sub(r"\s*Hunk Size:\s*", "", line).strip()
                elif re.findall(r"^Total Hunks:", line):
                    info["total_hunks"] = re.sub(
                        r"\s*Total Hunks:\s*", "", line
                    ).strip()
                elif re.findall(r"^Unit Size:", line):
                    info["unit_size"] = re.sub(r"\s*Unit Size:\s*", "", line).strip()
                elif re.findall(r"^Total Units:", line):
                    info["total_units"] = re.sub(
                        r"\s*Total Units:\s*", "", line
                    ).strip()
                elif re.findall(r"^CHD size:", line):
                    info["chd_size"] = re.sub(r"\s*CHD size:\s*", "", line).strip()
                elif re.findall(r"^Ratio:", line):
                    info["ratio"] = re.sub(r"\s*Ratio:\s*", "", line).strip()
                elif re.findall(r"^Data SHA1:", line):
                    info["data_sha1"] = re.sub(r"\s*Data SHA1:\s*", "", line).strip()
                elif re.findall(r"^Metadata:", line):
                    # Parse metadata which may span multiple lines
                    metadata_line = re.sub(r"\s*Metadata:\s*", "", line).strip()
                    if "Metadata" not in info:
                        info["metadata"] = []
                    info["metadata"].append(metadata_line)

            # Store the parsed version in the object
            if "file_version" in info:
                self.version = info["file_version"]

        except Exception as e:
            print(f"Error getting CHD info: {e}")
            info["error"] = str(e)

        return info

    @property
    def exists(self):
        """Check if the CHD file exists."""
        return self.path and os.path.exists(self.path)

    @property
    def is_valid(self):
        """Check if the CHD file is valid."""
        info = self._get_chd_info()
        return "error" not in info and "sha1" in info

    def _create(self):
        """
        Create the CHD file from the source.

        Returns:
            bool: True if successful, False otherwise
        """
        if self.path and self.exists:
            raise CHDAlreadyExistsException(str(self.path))

        else:
            if not self.toc_source:
                raise CHDSourceException(
                    f"toc file not found for {self.source.dat_game_entry.name}"
                )

            try:
                os.makedirs(self.output_path, exist_ok=True)
            except Exception as e:
                raise CHDCreationException(
                    f"Failed to create output directory {self.output_path}:", str(e)
                )

            try:
                command = [
                    "chdman",
                    "createcd",
                    "-i",
                    str(self.toc_source),
                    "-o",
                    str(self.path),
                ]
                subprocess.run(command, check=True)

                # Update properties after creation
                if self.exists:
                    self._initialize_from_existing(str(self.path))
                    self.preexisting = False
                    return True

            except subprocess.CalledProcessError as e:
                raise CHDCreationException(str(self.path), str(e))
                # print(f'CHD creation failed: {e}')

    def delete(self):
        """
        Delete the CHD file.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.exists:
                os.remove(self.path)
                return True
        except Exception as e:
            print(f"Error deleting CHD file: {e}")

        return False
