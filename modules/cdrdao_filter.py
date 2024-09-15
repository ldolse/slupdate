import os
from modules.ifilter import IFilter
from modules.error_number import ErrorNumber

class CDRDAOFilter(IFilter):
    def __init__(self, path: str):
        super().__init__(path)
        self._data_stream = None

    @property
    def name(self) -> str:
        return "CDRDAO"

    def identify(self, path: str) -> bool:
        if isinstance(path, CDRDAOFilter):
            path = path.path  # Use the path attribute if it's a CDRDAOFilter instance
        
        if not os.path.isfile(path):
            return False
        
        _, ext = os.path.splitext(path)
        if ext.lower() != '.toc':
            return False

        # Check the first few lines of the file for CDRDAO-specific content
        try:
            with open(path, 'r') as f:
                first_lines = [next(f) for _ in range(5)]
            return any('CD_DA' in line or 'CD_ROM' in line or 'CD_ROM_XA' in line for line in first_lines)
        except:
            return False

    def open(self, path: str) -> ErrorNumber:
        if isinstance(path, CDRDAOFilter):
            path = path.path  # Use the path attribute if it's a CDRDAOFilter instance
        if not self.identify(path):
            return ErrorNumber.InvalidArgument
        
        try:
            self._data_stream = open(path, 'rb')
            return ErrorNumber.NoError
        except IOError:
            return ErrorNumber.CannotOpenFile

    def get_data_fork_stream(self):
        return self._data_stream

    def close(self):
        if self._data_stream:
            self._data_stream.close()
            self._data_stream = None