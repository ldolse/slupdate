import os
import uuid
from datetime import datetime
from typing import Optional, BinaryIO
from modules.error_number import ErrorNumber

class IFilter:
    def __init__(self, path: str):
        self._path = path
        self._stream: Optional[BinaryIO] = None

    @property
    def name(self) -> str:
        return "Python IFilter"

    @property
    def id(self) -> uuid.UUID:
        return uuid.uuid4()  # This should be a constant UUID for each filter type

    @property
    def author(self) -> str:
        return "Aaru Python Port"

    @property
    def base_path(self) -> str:
        return self._path

    @property
    def creation_time(self) -> datetime:
        return datetime.fromtimestamp(os.path.getctime(self._path))

    @property
    def data_fork_length(self) -> int:
        return os.path.getsize(self._path)

    @property
    def filename(self) -> str:
        return os.path.basename(self._path)

    @property
    def last_write_time(self) -> datetime:
        return datetime.fromtimestamp(os.path.getmtime(self._path))

    @property
    def length(self) -> int:
        return os.path.getsize(self._path)

    @property
    def path(self) -> str:
        return self._path

    @property
    def parent_folder(self) -> str:
        return os.path.dirname(self._path)

    def close(self):
        if self._stream:
            self._stream.close()
            self._stream = None

    def get_data_fork_stream(self) -> BinaryIO:
        if not self._stream or self._stream.closed:
            self._stream = open(self._path, 'rb')
        return self._stream

    def identify(self, path: str) -> bool:
        # This method should be overridden by specific filter implementations
        return False

    def open(self, path: str) -> ErrorNumber:
        if not self.identify(path):
            return ErrorNumber.InvalidArgument
        
        try:
            self._stream = open(path, 'rb')
            return ErrorNumber.NoError
        except IOError:
            return ErrorNumber.CannotOpenFile

    def close(self):
        if self._stream:
            self._stream.close()
            self._stream = None