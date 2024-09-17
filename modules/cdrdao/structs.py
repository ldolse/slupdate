from dataclasses import dataclass, field
from typing import Dict, Optional, List
from modules.CD.cd_types import MediaType
from modules.ifilter import IFilter

@dataclass
class CdrdaoTrackFile:
    sequence: int = 0
    datafilter: Optional[IFilter] = None
    datafile: str = ""
    offset: int = 0
    filetype: str = ""

@dataclass
class CdrdaoTrack:
    sequence: int = 0
    title: str = ""
    genre: str = ""
    arranger: str = ""
    composer: str = ""
    performer: str = ""
    songwriter: str = ""
    isrc: str = ""
    message: str = ""
    trackfile: CdrdaoTrackFile = field(default_factory=CdrdaoTrackFile)
    indexes: Dict[int, int] = field(default_factory=dict)
    pregap: int = 0
    postgap: int = 0
    flag_dcp: bool = False
    flag_4ch: bool = False
    flag_pre: bool = False
    bps: int = 0
    sectors: int = 0
    start_sector: int = 0
    tracktype: str = ""
    subchannel: bool = False
    packedsubchannel: bool = False

@dataclass
class CdrdaoDisc:
    title: str = ""
    genre: str = ""
    arranger: str = ""
    composer: str = ""
    performer: str = ""
    songwriter: str = ""
    message: str = ""
    mcn: str = ""
    disktype: MediaType = MediaType.Unknown
    disktypestr: str = ""
    disk_id: str = ""
    barcode: str = ""
    tracks: List[CdrdaoTrack] = field(default_factory=list)
    comment: str = ""
