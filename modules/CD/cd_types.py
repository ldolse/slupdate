from dataclasses import dataclass, field
from functools import total_ordering
from typing import List, Optional, Dict

from datetime import datetime
from enum import IntEnum, Flag

class TrackSubchannelType(IntEnum):
    None_ = 0
    Packed = 1
    Raw = 2
    PackedInterleaved = 3
    RawInterleaved = 4
    Q16 = 5
    Q16Interleaved = 6

class TrackType(IntEnum):
    Audio = 0
    Data = 1
    CdMode1 = 2
    CdMode2Formless = 3
    CdMode2Form1 = 4
    CdMode2Form2 = 5

class TocAdr(IntEnum):
    NoInformation = 0x00
    CurrentPosition = 0x01
    MediaCatalogNumber = 0x02
    ISRC = 0x03
    TrackPointer = 0x01
    VideoTrackPointer = 0x04

class TocControl(IntEnum):
    TwoChanNoPreEmph = 0x00
    TwoChanPreEmph = 0x01
    CopyPermissionMask = 0x02
    DataTrack = 0x04
    DataTrackIncremental = 0x05
    FourChanNoPreEmph = 0x08
    FourChanPreEmph = 0x09
    ReservedMask = 0x0C

class SectorTagType(IntEnum):
    AppleSectorTag = 0
    CdSectorSync = 1
    CdSectorHeader = 2
    CdSectorSubHeader = 3
    CdSectorEdc = 4
    CdSectorEccP = 5
    CdSectorEccQ = 6
    CdSectorEcc = 7
    CdSectorSubchannel = 8
    CdTrackIsrc = 9
    CdTrackText = 10
    CdTrackFlags = 11
    DvdSectorCmi = 12
    FloppyAddressMark = 13
    DvdSectorTitleKey = 14
    DvdTitleKeyDecrypted = 15
    DvdSectorInformation = 16
    DvdSectorNumber = 17
    DvdSectorIed = 18
    DvdSectorEdc = 19

class MediaTagType(IntEnum):
    CD_TOC = 0
    CD_SessionInfo = 1
    CD_FullTOC = 2
    CD_PMA = 3
    CD_ATIP = 4
    CD_TEXT = 5
    CD_MCN = 6
    DVD_PFI = 7
    DVD_CMI = 8
    DVD_DiscKey = 9
    DVD_BCA = 10
    DVD_DMI = 11
    DVD_MediaIdentifier = 12
    DVD_MKB = 13
    DVDRAM_DDS = 14
    DVDRAM_MediumStatus = 15
    DVDRAM_SpareArea = 16
    DVDR_RMD = 17
    DVDR_PreRecordedInfo = 18
    DVDR_MediaIdentifier = 19
    DVDR_PFI = 20
    DVD_ADIP = 21
    HDDVD_CPI = 22
    HDDVD_MediumStatus = 23
    DVDDL_LayerCapacity = 24
    DVDDL_MiddleZoneAddress = 25
    DVDDL_JumpIntervalSize = 26
    DVDDL_ManualLayerJumpLBA = 27
    BD_DI = 28
    BD_BCA = 29
    BD_DDS = 30
    BD_CartridgeStatus = 31
    BD_SpareArea = 32
    AACS_VolumeIdentifier = 33
    AACS_SerialNumber = 34
    AACS_MediaIdentifier = 35
    AACS_MKB = 36
    AACS_DataKeys = 37
    AACS_LBAExtents = 38
    AACS_CPRM_MKB = 39
    Hybrid_RecognizedLayers = 40
    MMC_WriteProtection = 41
    MMC_DiscInformation = 42
    MMC_TrackResourcesInformation = 43
    MMC_POWResourcesInformation = 44
    SCSI_INQUIRY = 45
    SCSI_MODEPAGE_2A = 46
    ATA_IDENTIFY = 47
    ATAPI_IDENTIFY = 48
    PCMCIA_CIS = 49
    SD_CID = 50
    SD_CSD = 51
    SD_SCR = 52
    SD_OCR = 53
    MMC_CID = 54
    MMC_CSD = 55
    MMC_OCR = 56
    MMC_ExtendedCSD = 57
    Xbox_SecuritySector = 58
    Floppy_LeadOut = 59
    DCB = 60
    CD_FirstTrackPregap = 61
    CD_LeadOut = 62
    SCSI_MODESENSE_6 = 63
    SCSI_MODESENSE_10 = 64
    USB_Descriptors = 65
    Xbox_DMI = 66
    Xbox_PFI = 67
    CD_LeadIn = 68
    MiniDiscType = 69
    MiniDiscD5 = 70
    MiniDiscUTOC = 71
    MiniDiscDTOC = 72
    DVD_DiscKey_Decrypted = 73

class MetadataMediaType(IntEnum):
    OpticalDisc = 0
    BlockMedia = 1
    LinearMedia = 2
    AudioMedia = 3

class CdFlags(Flag):
    FourChannel = 0x08
    DataTrack = 0x04
    CopyPermitted = 0x02
    PreEmphasis = 0x01

class OpticalImageCapabilities(Flag):
    CanStoreAudioTracks = 0x01
    CanStoreVideoTracks = 0x02
    CanStoreDataTracks = 0x03
    CanStorePregaps = 0x04
    CanStoreIndexes = 0x08
    CanStoreSubchannelRw = 0x10
    CanStoreSessions = 0x20
    CanStoreIsrc = 0x40
    CanStoreCdText = 0x80
    CanStoreMcn = 0x100
    CanStoreRawData = 0x200
    CanStoreNotCdSessions = 0x2000
    CanStoreNotCdTracks = 0x4000
    CanStoreHiddenTracks = 0x8000
    CanStoreScrambledData = 0x400
    CanStoreCookedData = 0x800
    CanStoreMultipleTracks = 0x1000

class MediaEncoding(IntEnum):
    Unknown = 0
    FM = 1
    MFM = 2
    M2FM = 3
    AppleGCR = 4
    CommodoreGCR = 5

class MediaType(IntEnum):
    Unknown = 0
    UnknownMO = 1
    GENERIC_HDD = 2
    Microdrive = 3
    Zone_HDD = 4
    FlashDrive = 5
    UnknownTape = 6
    CD = 10
    CDDA = 11
    CDG = 12
    CDEG = 13
    CDI = 14
    CDROM = 15
    CDROMXA = 16
    CDPLUS = 17
    CDMO = 18
    CDR = 19
    CDRW = 20
    CDMRW = 21
    VCD = 22
    SVCD = 23
    PCD = 24
    SACD = 25
    DDCD = 26
    DDCDR = 27
    DDCDRW = 28
    DTSCD = 29
    CDMIDI = 30
    CDV = 31
    PD650 = 32
    PD650_WORM = 33
    CDIREADY = 34
    FMTOWNS = 35
    EVD = 70
    FVD = 71
    HVD = 72
    CBHD = 73
    HDVMD = 74
    VCDHD = 75
    SVOD = 76
    FDDVD = 77
    CVD = 78
    PlayStationMemoryCard = 110
    PlayStationMemoryCard2 = 111
    PS1CD = 112
    PS2CD = 113
    PS2DVD = 114
    PS3DVD = 115
    PS3BD = 116
    PS4BD = 117
    UMD = 118
    PlayStationVitaGameCard = 119
    PS5BD = 120
    XGD = 130
    XGD2 = 131
    XGD3 = 132
    XGD4 = 133
    MEGACD = 150
    SATURNCD = 151
    GDROM = 152
    GDR = 153
    SegaCard = 154
    MilCD = 155
    MegaDriveCartridge = 156
    _32XCartridge = 157
    SegaPicoCartridge = 158
    MasterSystemCartridge = 159
    GameGearCartridge = 160
    SegaSaturnCartridge = 161
    HuCard = 170
    SuperCDROM2 = 171
    JaguarCD = 172
    ThreeDO = 173
    PCFX = 174
    NeoGeoCD = 175
    CDTV = 176
    CD32 = 177
    Nuon = 178
    Playdia = 179
    AtariLynxCard = 821
    AtariJaguarCartridge = 822

@dataclass
class ImageInfo:
    has_partitions: bool = False
    has_sessions: bool = False
    image_size: int = 0
    sectors: int = 0
    sector_size: int = 0
    readable_media_tags: List[MediaTagType] = field(default_factory=list)
    readable_sector_tags: List[SectorTagType] = field(default_factory=list)
    version: Optional[str] = None
    application: Optional[str] = None
    application_version: Optional[str] = None
    creator: Optional[str] = None
    creation_time: Optional[datetime] = None
    last_modification_time: Optional[datetime] = None
    media_title: Optional[str] = None
    comments: Optional[str] = None
    media_manufacturer: Optional[str] = None
    media_model: Optional[str] = None
    media_serial_number: Optional[str] = None
    media_barcode: Optional[str] = None
    media_part_number: Optional[str] = None
    media_type: Optional[MediaType] = None
    media_sequence: int = 0
    last_media_sequence: int = 0
    drive_manufacturer: Optional[str] = None
    drive_model: Optional[str] = None
    drive_serial_number: Optional[str] = None
    drive_firmware_revision: Optional[str] = None
    metadata_media_type: Optional[MetadataMediaType] = None
    cylinders: int = 0
    heads: int = 0
    sectors_per_track: int = 0

@dataclass
class Session:
    sequence: int = 0
    start_track: int = 0
    end_track: int = 0
    start_sector: int = 0
    end_sector: int = 0

@dataclass
class Track:
    bytes_per_sector: int = 0
    description: str = ""
    end_sector: int = 0
    file: str = ""
    file_offset: int = 0
    file_type: str = ""
    filter: Optional['IFilter'] = None
    indexes: Dict[int, int] = field(default_factory=dict)
    pregap: int = 0
    raw_bytes_per_sector: int = 0
    sequence: int = 0
    session: int = 0
    start_sector: int = 0
    subchannel_file: str = ""
    subchannel_filter: Optional['IFilter'] = None
    subchannel_offset: int = 0
    subchannel_type: TrackSubchannelType = TrackSubchannelType.None_
    type: TrackType = TrackType.Audio

@total_ordering
@dataclass
class Partition:
    sequence: int = 0
    type: str = ""
    name: str = ""
    offset: int = 0
    start: int = 0
    size: int = 0
    length: int = 0
    description: str = ""
    scheme: str = ""

    @property
    def end(self) -> int:
        return self.start + self.length - 1

    def __eq__(self, other):
        if not isinstance(other, Partition):
            return NotImplemented
        return self.start == other.start and self.length == other.length

    def __lt__(self, other):
        if not isinstance(other, Partition):
            return NotImplemented
        return (self.start, self.end) < (other.start, other.end)

    def __hash__(self):
        return hash((self.start, self.end))

def enum_name(enum_class, value):
    try:
        return enum_class(value).name
    except ValueError:
        return f"Unknown_{value}"
