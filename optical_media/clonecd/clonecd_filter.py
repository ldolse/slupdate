import os
from typing import BinaryIO
from modules.ifilter import IFilter
from modules.error_number import ErrorNumber
import logging

logger = logging.getLogger(__name__)

class CloneCDFilter(IFilter):
    def __init__(self, path: str):
        super().__init__(path)
        self._img_path = None
        self._sub_path = None
        self._ccd_stream = None

    @property
    def name(self) -> str:
        return "CloneCD"

    def identify(self, path: str) -> bool:
        logger.debug(f"Attempting to identify file: {path}")
        if not os.path.isfile(path):
            logger.debug(f"File does not exist: {path}")
            return False
        
        _, ext = os.path.splitext(path)
        if ext.lower() != '.ccd':
            logger.debug(f"File extension is not .ccd: {ext}")
            return False

        # Check for the presence of .img and .sub files
        base_path = path[:-4]  # Remove .ccd extension
        self._img_path = f"{base_path}.img"
        self._sub_path = f"{base_path}.sub"
        img_exists = os.path.isfile(self._img_path)
        sub_exists = os.path.isfile(self._sub_path)
        logger.debug(f".img file exists: {img_exists}, .sub file exists: {sub_exists}")
        return img_exists and sub_exists

    def open(self, path: str) -> ErrorNumber:
        if not self.identify(path):
            return ErrorNumber.InvalidArgument
        
        try:
            self._stream = open(path, 'rb')
            return ErrorNumber.NoError
        except IOError:
            return ErrorNumber.CannotOpenFile

    def get_ccd_stream(self) -> BinaryIO:
        if not self._ccd_stream or self._ccd_stream.closed:
            self._ccd_stream = open(self._path, 'rb')
        return self._ccd_stream

    def get_img_stream(self) -> BinaryIO:
        return open(self._img_path, 'rb')

    def get_sub_stream(self) -> BinaryIO:
        return open(self._sub_path, 'rb')

    def close(self):
        super().close()
        if self._ccd_stream:
            self._ccd_stream.close()
            self._ccd_stream = None