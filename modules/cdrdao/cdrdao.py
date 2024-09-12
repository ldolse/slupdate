import io
import re
import os
from datetime import datetime
from typing import List, Dict, Optional

from modules.CD.atip import ATIP
from modules.CD.sector import Sector
from modules.CD.subchannel import Subchannel
from modules.CD.cd_types import (
    TrackType, TrackSubchannelType, SectorTagType, MediaType, 
    MediaTagType, MetadataMediaType, TocControl,
    Track, Session, Partition, ImageInfo
)
from modules.error_number import ErrorNumber
from modules.ifilter import IFilter

from .constants import *
from .helpers import *
from .identify import identify
from .properties import *
from .read import CdrdaoRead
from .structs import CdrdaoTrackFile, CdrdaoTrack, CdrdaoDisc
from .write import *

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Cdrdao(CdrdaoProperties):
    MODULE_NAME = "CDRDAO plugin"

    def __init__(self):
        super().__init__()
        self.reader = CdrdaoRead(self)
        self._catalog: Optional[str] = None
        self._cdrdao_filter: Optional[IFilter] = None
        self._cdtext: Optional[bytes] = None
        self._cue_stream = None
        self._data_filter: Optional[IFilter] = None
        self._data_stream = None
        self._descriptor_stream = None
        self._full_toc: Optional[bytes] = None
        self._image_info = ImageInfo(
            readable_sector_tags=[],
            readable_media_tags=[],
            has_partitions=True,
            has_sessions=True,
            version=None,
            application="CDRDAO",
            application_version=None,
            media_title=None,
            creator=None,
            media_manufacturer=None,
            media_model=None,
            media_part_number=None,
            media_sequence=0,
            last_media_sequence=0,
            drive_manufacturer=None,
            drive_model=None,
            drive_serial_number=None,
            drive_firmware_revision=None
        )
        self._offset_map: Dict[int, int] = {}
        self._scrambled: bool = False
        self._sub_filter: Optional[IFilter] = None
        self._sub_stream = None
        self._track_flags: Dict[int, int] = {}
        self._writing_base_name: Optional[str] = None

        self.partitions: List[Partition] = []
        self.tracks: List[Track] = []
        self.sessions: List[Session] = []
        self._is_writing: bool = False
        self._error_message: Optional[str] = None
        self._discimage: CdrdaoDisc = CdrdaoDisc()

