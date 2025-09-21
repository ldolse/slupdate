import os
import pathlib
import re
import subprocess

class CHD:
    """
    Represents a CHD (Compressed Hunks of Data) file as a Python object.
    
    This class provides functionality to create, read, and manipulate CHD files,
    with properties that are set either during creation or by parsing an existing CHD.
    """
    
    def __init__(self, chd_path=None, source_file=None, output_path=None):
        """
        Initialize a CHD object.
        
        Args:
            chd_path (str): Path to an existing CHD file for reading
            source_file (str): Source file path when creating a new CHD
            output_path (str): Output path for the created CHD
        """
        # Properties set during initialization or by parsing existing CHD
        self.path = None  # Path to the CHD file
        self.name = None  # Name of the CHD (without extension)
        self.extension = '.chd'  # File extension
        self.size = 0  # Size in bytes
        self.sha1 = None  # SHA1 hash
        self.parent_sha = None  # Parent CHD SHA1 if applicable
        self.logical_size = None  # Logical size of the original data
        self.compression = None  # Compression type used
        
        if chd_path and os.path.exists(chd_path):
            # Initialize from existing CHD file
            self._initialize_from_existing(chd_path)
        elif source_file and output_path:
            # Initialize for CHD creation
            self._initialize_for_creation(source_file, output_path)
        else:
            raise ValueError("Either provide chd_path for reading or both source_file and output_path for creation")
    
    def _initialize_from_existing(self, chd_path):
        """
        Initialize CHD object from an existing CHD file.
        
        Args:
            chd_path (str): Path to the existing CHD file
        """
        self.path = pathlib.Path(chd_path)
        self.name = self.path.stem
        self.size = os.path.getsize(chd_path)
        
        # Get CHD information
        info = self._get_chd_info()
        if info:
            self.sha1 = info.get('sha1')
            self.parent_sha = info.get('parent_sha')
            self.logical_size = info.get('logical_size')
            self.compression = info.get('compression')
    
    def _initialize_for_creation(self, source_file, output_path):
        """
        Initialize CHD object for creation.
        
        Args:
            source_file (str): Path to the source file (CUE, ISO, etc.)
            output_path (str): Path where the CHD will be created
        """
        self.source_file = pathlib.Path(source_file)
        self.path = pathlib.Path(output_path)
        self.name = self.path.stem
    
    def _get_chd_info(self):
        """
        Get information about the CHD file using chdman.
        
        Returns:
            dict: Dictionary containing CHD information
        """
        if not os.path.exists(self.path):
            return {"error": "CHD file does not exist"}
            
        info = {}
        
        try:
            command = ['chdman', 'info', '-i', str(self.path)]
            proc = subprocess.Popen(command, stdout=subprocess.PIPE)
            output = proc.stdout.read().decode('ascii').split('\n')
            
            for line in output:
                if re.findall(r'^\s*SHA1', line):
                    info['sha1'] = re.sub(r'\s*SHA1:\s*', '', line).strip()
                elif re.findall(r'^\s*Parent SHA', line):
                    info['parent_sha'] = re.sub(r'\s*Parent SHA:\s*', '', line).strip()
                elif re.findall(r'^\s*Logical', line):
                    info['logical_size'] = re.sub(r'\s*Logical size:\s*', '', line).strip()
                elif re.findall(r'^\s*Compression', line):
                    info['compression'] = re.sub(r'\s*Compression:\s*', '', line).strip()
                    
        except Exception as e:
            print(f'Error getting CHD info: {e}')
            info['error'] = str(e)
            
        return info
    
    @property
    def exists(self):
        """Check if the CHD file exists."""
        return self.path and os.path.exists(self.path)
    
    @property
    def is_valid(self):
        """Check if the CHD file is valid."""
        info = self._get_chd_info()
        return 'error' not in info and 'sha1' in info
    
    def create(self):
        """
        Create the CHD file from the source.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not hasattr(self, 'source_file') or not self.source_file:
            print("No source file specified for CHD creation")
            return False
            
        try:
            command = ['chdman', 'createcd', '-i', str(self.source_file), '-o', str(self.path)]
            subprocess.run(command, check=True)
            
            # Update properties after creation
            if self.exists:
                self._initialize_from_existing(str(self.path))
                return True
                
        except subprocess.CalledProcessError as e:
            print(f'CHD creation failed: {e}')
            
        return False
    
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
            print(f'Error deleting CHD file: {e}')
            
        return False
