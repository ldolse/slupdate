import os
from modules.ifilter import IFilter
from modules.error_number import ErrorNumber

class CDRDAOFilter(IFilter):
    def __init__(self, path: str):
        super().__init__(path)

    @property
    def name(self) -> str:
        return "CDRDAO"

    def identify(self, path: str) -> bool:
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
        if not self.identify(path):
            return ErrorNumber.InvalidArgument
        
        return super().open(path)
