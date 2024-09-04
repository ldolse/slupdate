import io
import re
import os
import struct
from datetime import datetime
from typing import Tuple, List, Dict, Optional, Union
from dataclasses import dataclass, field

from modules.CD.atip import ATIP
from modules.CD.fulltoc import FullTOC, TrackDataDescriptor, CDFullTOC
from modules.CD.sector import Sector
from modules.CD.subchannel import Subchannel
from modules.CD.cd_types import (
    TrackType, TrackSubchannelType, SectorTagType, MediaType, 
    MediaTagType, MetadataMediaType, TocControl, OpticalImageCapabilities,
    Track, Session, Partition, ImageInfo
)
from modules.error_number import ErrorNumber
from modules.ifilter import IFilter
from modules.CD.checksums import CdChecksums

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

class Cdrdao:
    MODULE_NAME = "CDRDAO plugin"

    # Constants
    CDRDAO_TRACK_TYPE_AUDIO = "AUDIO"
    CDRDAO_TRACK_TYPE_MODE1 = "MODE1"
    CDRDAO_TRACK_TYPE_MODE1_RAW = "MODE1_RAW"
    CDRDAO_TRACK_TYPE_MODE2 = "MODE2"
    CDRDAO_TRACK_TYPE_MODE2_FORM1 = "MODE2_FORM1"
    CDRDAO_TRACK_TYPE_MODE2_FORM2 = "MODE2_FORM2"
    CDRDAO_TRACK_TYPE_MODE2_MIX = "MODE2_FORM_MIX"
    CDRDAO_TRACK_TYPE_MODE2_RAW = "MODE2_RAW"

    # Regular expressions
    REGEX_COMMENT = r'^\s*\/\/(?P<comment>.+)$'
    REGEX_COPY = r'^\s*(?P<no>NO)?\s*COPY'
    REGEX_DISCTYPE = r'^\s*(?P<type>(CD_DA|CD_ROM_XA|CD_ROM|CD_I))'
    REGEX_EMPHASIS = r'^\s*(?P<no>NO)?\s*PRE_EMPHASIS'
    REGEX_FILE_AUDIO = r'^\s*(AUDIO)?FILE\s*"(?P<filename>.+)"\s*(#(?P<base_offset>\d+))?\s*((?P<start>[\d]+:[\d]+:[\d]+)|(?P<start_num>\d+))\s*(?P<length>[\d]+:[\d]+:[\d]+)?'
    REGEX_FILE_DATA = r'^\s*DATAFILE\s*"(?P<filename>.+)"\s*(#(?P<base_offset>\d+))?\s*(?P<length>[\d]+:[\d]+:[\d]+)?'
    REGEX_INDEX = r'^\s*INDEX\s*(?P<address>\d+:\d+:\d+)'
    REGEX_ISRC = r'^\s*ISRC\s*"(?P<isrc>[A-Z0-9]{5,5}[0-9]{7,7})"'
    REGEX_MCN = r'^\s*CATALOG\s*"(?P<catalog>[\x21-\x7F]{13,13})"'
    REGEX_PREGAP = r'^\s*START\s*(?P<address>\d+:\d+:\d+)?'
    REGEX_STEREO = r'^\s*(?P<num>(TWO|FOUR))_CHANNEL_AUDIO'
    REGEX_TRACK = r'^\s*TRACK\s*(?P<type>(AUDIO|MODE1_RAW|MODE1|MODE2_FORM1|MODE2_FORM2|MODE2_FORM_MIX|MODE2_RAW|MODE2))\s*(?P<subchan>(RW_RAW|RW))?'
    REGEX_ZERO_AUDIO = r'^\s*SILENCE\s*(?P<length>\d+:\d+:\d+)'
    REGEX_ZERO_DATA = r'^\s*ZERO\s*(?P<length>\d+:\d+:\d+)'
    REGEX_ZERO_PREGAP = r'^\s*PREGAP\s*(?P<length>\d+:\d+:\d+)'

    # CD-Text related regex
    REGEX_ARRANGER = r'^\s*ARRANGER\s*"(?P<arranger>.+)"'
    REGEX_COMPOSER = r'^\s*COMPOSER\s*"(?P<composer>.+)"'
    REGEX_DISC_ID = r'^\s*DISC_ID\s*"(?P<discid>.+)"'
    REGEX_MESSAGE = r'^\s*MESSAGE\s*"(?P<message>.+)"'
    REGEX_PERFORMER = r'^\s*PERFORMER\s*"(?P<performer>.+)"'
    REGEX_SONGWRITER = r'^\s*SONGWRITER\s*"(?P<songwriter>.+)"'
    REGEX_TITLE = r'^\s*TITLE\s*"(?P<title>.+)"'
    REGEX_UPC = r'^\s*UPC_EAN\s*"(?P<catalog>[\d]{13,13})"'

    # Unused regex
    REGEX_CD_TEXT = r'^\s*CD_TEXT\s*\{'
    REGEX_CLOSURE = r'^\s*\}'
    REGEX_LANGUAGE = r'^\s*LANGUAGE\s*(?P<code>\d+)\s*\{'
    REGEX_LANGUAGE_MAP = r'^\s*LANGUAGE_MAP\s*\{'
    REGEX_LANGUAGE_MAPPING = r'^\s*(?P<code>\d+)\s?\:\s?(?P<language>\d+|\w+)'

    def __init__(self):
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

    @property
    def optical_capabilities(self) -> OpticalImageCapabilities:
        return (OpticalImageCapabilities.CanStoreAudioTracks |
                OpticalImageCapabilities.CanStoreDataTracks |
                OpticalImageCapabilities.CanStorePregaps |
                OpticalImageCapabilities.CanStoreSubchannelRw |
                OpticalImageCapabilities.CanStoreIsrc |
                OpticalImageCapabilities.CanStoreCdText |
                OpticalImageCapabilities.CanStoreMcn |
                OpticalImageCapabilities.CanStoreRawData |
                OpticalImageCapabilities.CanStoreCookedData |
                OpticalImageCapabilities.CanStoreMultipleTracks |
                OpticalImageCapabilities.CanStoreIndexes)

    @property
    def info(self) -> ImageInfo:
        return self._image_info

    @property
    def name(self) -> str:
        return "CDRDAO"

    @property
    def id(self) -> str:
        return "04D7BA12-1BE8-44D4-97A4-1B48A505463E"

    @property
    def format(self) -> str:
        return "CDRDAO tocfile"

    @property
    def dump_hardware(self) -> List['DumpHardware']:
        return None

    @property
    def aaru_metadata(self) -> Optional['Metadata']:
        return None

    @property
    def supported_media_tags(self) -> List[MediaTagType]:
        return [MediaTagType.CD_MCN]

    @property
    def supported_sector_tags(self) -> List[SectorTagType]:
        return [
            SectorTagType.CdSectorEcc,
            SectorTagType.CdSectorEccP,
            SectorTagType.CdSectorEccQ,
            SectorTagType.CdSectorEdc,
            SectorTagType.CdSectorHeader,
            SectorTagType.CdSectorSubchannel,
            SectorTagType.CdSectorSubHeader,
            SectorTagType.CdSectorSync,
            SectorTagType.CdTrackFlags,
            SectorTagType.CdTrackIsrc
        ]

    @property
    def supported_media_types(self) -> List[MediaType]:
        return [
            MediaType.CD, MediaType.CDDA, MediaType.CDEG, MediaType.CDG, MediaType.CDI,
            MediaType.CDMIDI, MediaType.CDMRW, MediaType.CDPLUS, MediaType.CDR,
            MediaType.CDROM, MediaType.CDROMXA, MediaType.CDRW, MediaType.CDV,
            MediaType.DDCD, MediaType.DDCDR, MediaType.DDCDRW, MediaType.MEGACD,
            MediaType.PS1CD, MediaType.PS2CD, MediaType.SuperCDROM2, MediaType.SVCD,
            MediaType.SATURNCD, MediaType.ThreeDO, MediaType.VCD, MediaType.VCDHD,
            MediaType.NeoGeoCD, MediaType.PCFX, MediaType.CDTV, MediaType.CD32,
            MediaType.Nuon, MediaType.Playdia, MediaType.PCD
        ]

    @property
    def supported_options(self) -> List[Tuple[str, Type, str, Any]]:
        return [
            ("separate", bool, "Write each track to a separate file", False)
        ]

    @property
    def known_extensions(self) -> List[str]:
        return [".toc"]

    @property
    def is_writing(self) -> bool:
        return self._is_writing

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    def _parse_cd_text(self, cd_text_data: bytes) -> None:
        if not cd_text_data:
            return
    
        pack_type = 0
        track_number = 0
        block_number = 0
        text_buffer = bytearray()
    
        for i in range(0, len(cd_text_data), 18):
            pack = cd_text_data[i:i+18]
            pack_type = pack[0] & 0x0F
            track_number = pack[1]
            block_number = pack[2]
            text = pack[4:16]
    
            if pack_type == 0x80:
                text_buffer.extend(text)
                if pack[3] & 0x80:
                    self._process_cd_text(pack_type, track_number, text_buffer.decode('ascii', errors='ignore'))
                    text_buffer.clear()
            else:
                self._process_cd_text(pack_type, track_number, text.decode('ascii', errors='ignore'))

    def _process_cd_text(self, pack_type: int, track_number: int, text: str) -> None:
        if track_number == 0:
            self._process_disc_cd_text(pack_type, text)
        else:
            self._process_track_cd_text(pack_type, track_number, text)

    def _process_disc_cd_text(self, pack_type: int, text: str) -> None:
        if pack_type == 0x80:
            self._discimage.title = text
        elif pack_type == 0x81:
            self._discimage.performer = text
        elif pack_type == 0x82:
            self._discimage.songwriter = text
        elif pack_type == 0x83:
            self._discimage.composer = text
        elif pack_type == 0x84:
            self._discimage.arranger = text
        elif pack_type == 0x85:
            self._discimage.message = text
        elif pack_type == 0x86:
            self._discimage.disk_id = text
        elif pack_type == 0x87:
            self._discimage.genre = text
        elif pack_type == 0x8E:
            self._discimage.barcode = text

    def _process_track_cd_text(self, pack_type: int, track_number: int, text: str) -> None:
        track = next((t for t in self._discimage.tracks if t.sequence == track_number), None)
        if track:
            if pack_type == 0x80:
                track.title = text
            elif pack_type == 0x81:
                track.performer = text
            elif pack_type == 0x82:
                track.songwriter = text
            elif pack_type == 0x83:
                track.composer = text
            elif pack_type == 0x84:
                track.arranger = text
            elif pack_type == 0x85:
                track.message = text
            elif pack_type == 0x86:
                track.isrc = text
            elif pack_type == 0x87:
                track.genre = text

    def _determine_media_type(self):
        data_tracks = sum(1 for track in self._discimage.tracks if track.tracktype != self.CDRDAO_TRACK_TYPE_AUDIO)
        audio_tracks = len(self._discimage.tracks) - data_tracks
        mode2_tracks = sum(1 for track in self._discimage.tracks if track.tracktype in [
            self.CDRDAO_TRACK_TYPE_MODE2, self.CDRDAO_TRACK_TYPE_MODE2_FORM1, 
            self.CDRDAO_TRACK_TYPE_MODE2_FORM2, self.CDRDAO_TRACK_TYPE_MODE2_MIX, 
            self.CDRDAO_TRACK_TYPE_MODE2_RAW
        ])
        
        if data_tracks == 0:
            return MediaType.CDDA
        elif self._discimage.tracks[0].tracktype == self.CDRDAO_TRACK_TYPE_AUDIO and data_tracks > 0 and len(self.sessions) > 1 and mode2_tracks > 0:
            return MediaType.CDPLUS
        elif (self._discimage.tracks[0].tracktype != self.CDRDAO_TRACK_TYPE_AUDIO and audio_tracks > 0) or mode2_tracks > 0:
            return MediaType.CDROMXA
        elif audio_tracks == 0:
            return MediaType.CDROM
        else:
            return MediaType.CD

    @staticmethod
    def cdrdao_track_type_to_cooked_bytes_per_sector(track_type):
        if track_type in [Cdrdao.CDRDAO_TRACK_TYPE_MODE1, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM1, Cdrdao.CDRDAO_TRACK_TYPE_MODE1_RAW]:
            return 2048
        elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM2:
            return 2324
        elif track_type in [Cdrdao.CDRDAO_TRACK_TYPE_MODE2, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_MIX, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_RAW]:
            return 2336
        elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_AUDIO:
            return 2352
        else:
            return 0

    @staticmethod
    def cdrdao_track_type_to_track_type(track_type):
        if track_type in [Cdrdao.CDRDAO_TRACK_TYPE_MODE1, Cdrdao.CDRDAO_TRACK_TYPE_MODE1_RAW]:
            return TrackType.CdMode1
        elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM1:
            return TrackType.CdMode2Form1
        elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM2:
            return TrackType.CdMode2Form2
        elif track_type in [Cdrdao.CDRDAO_TRACK_TYPE_MODE2, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_MIX, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_RAW]:
            return TrackType.CdMode2Formless
        elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_AUDIO:
            return TrackType.Audio
        else:
            return TrackType.Data

    def _create_full_toc(self) -> None:
        toc = CDFullTOC()
        session_ending_track = {}
        toc.first_complete_session = 255
        toc.last_complete_session = 0
        track_descriptors = []
        current_track = 0

        for track in sorted(self._discimage.tracks, key=lambda t: t.sequence):
            if track.sequence < toc.first_complete_session:
                toc.first_complete_session = track.sequence

            if track.sequence <= toc.last_complete_session:
                current_track = track.sequence
                continue

            if toc.last_complete_session > 0:
                session_ending_track[toc.last_complete_session] = current_track

            toc.last_complete_session = track.sequence

        session_ending_track[toc.last_complete_session] = max(t.sequence for t in self._discimage.tracks)

        current_session = 0

        for track in sorted(self._discimage.tracks, key=lambda t: t.sequence):
            track_control = self._track_flags.get(track.sequence, 0)

            if track_control == 0 and track.tracktype != self.CDRDAO_TRACK_TYPE_AUDIO:
                track_control = 0x04  # Data track flag

            # Lead-Out
            if track.sequence > current_session and current_session != 0:
                leadout_amsf = self.lba_to_msf(track.start_sector - 150) # subtract 150 for lead-in
                leadout_pmsf = self.lba_to_msf(max(t.start_sector for t in self._discimage.tracks))

                # Lead-out
                track_descriptors.append(TrackDataDescriptor(
                    session_number=current_session,
                    point=0xB0,
                    adr=5,
                    control=0,
                    hour=0,
                    min=leadout_amsf[0],
                    sec=leadout_amsf[1],
                    frame=leadout_amsf[2],
                    phour=2,
                    pmin=leadout_pmsf[0],
                    psec=leadout_pmsf[1],
                    pframe=leadout_pmsf[2]
                ))

            # Lead-in
            if track.sequence > current_session:
                current_session = track.sequence
                ending_track_number = session_ending_track.get(current_session, 0)

                leadin_pmsf = self.lba_to_msf(next((t.start_sector + t.sectors for t in self._discimage.tracks if t.sequence == ending_track_number), 0))

                # Starting track
                track_descriptors.append(TrackDataDescriptor(
                    session_number=current_session,
                    point=0xA0,
                    adr=1,
                    control=track_control,
                    pmin=track.sequence
                ))

                # Ending track
                track_descriptors.append(TrackDataDescriptor(
                    session_number=current_session,
                    point=0xA1,
                    adr=1,
                    control=track_control,
                    pmin=ending_track_number
                ))

                # Lead-out start
                track_descriptors.append(TrackDataDescriptor(
                    session_number=current_session,
                    point=0xA2,
                    adr=1,
                    control=track_control,
                    phour=0,
                    pmin=leadin_pmsf[0],
                    psec=leadin_pmsf[1],
                    pframe=leadin_pmsf[2]
                ))

            pmsf = self.lba_to_msf(track.indexes.get(1, track.start_sector))

            # Track
            track_descriptors.append(TrackDataDescriptor(
                session_number=track.sequence,
                point=track.sequence,
                adr=1,
                control=track_control,
                phour=0,
                pmin=pmsf[0],
                psec=pmsf[1],
                pframe=pmsf[2]
            ))

        toc.track_descriptors = track_descriptors

        # Create binary representation
        toc_ms = io.BytesIO()
        toc_ms.write(struct.pack('>H', len(track_descriptors) * 11 + 2))  # DataLength
        toc_ms.write(bytes([toc.first_complete_session, toc.last_complete_session]))

        for descriptor in toc.track_descriptors:
            toc_ms.write(bytes([
                descriptor.session_number,
                (descriptor.adr << 4) | descriptor.control,
                descriptor.tno,
                descriptor.point,
                descriptor.min,
                descriptor.sec,
                descriptor.frame,
                descriptor.zero,
                descriptor.pmin,
                descriptor.psec,
                descriptor.pframe
            ]))

        self._full_toc = toc_ms.getvalue()

    @staticmethod
    def lba_to_msf(sector):
        return (sector // 75 // 60, (sector // 75) % 60, sector % 75)

    @staticmethod
    def get_track_mode(track):
        if track.type == TrackType.Audio and track.raw_bytes_per_sector == 2352:
            return Cdrdao.CDRDAO_TRACK_TYPE_AUDIO
        elif track.type == TrackType.Data:
            return Cdrdao.CDRDAO_TRACK_TYPE_MODE1
        elif track.type == TrackType.CdMode1 and track.raw_bytes_per_sector == 2352:
            return Cdrdao.CDRDAO_TRACK_TYPE_MODE1_RAW
        elif track.type == TrackType.CdMode2Formless and track.raw_bytes_per_sector != 2352:
            return Cdrdao.CDRDAO_TRACK_TYPE_MODE2
        elif track.type == TrackType.CdMode2Form1 and track.raw_bytes_per_sector != 2352:
            return Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM1
        elif track.type == TrackType.CdMode2Form2 and track.raw_bytes_per_sector != 2352:
            return Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM2
        elif track.type in [TrackType.CdMode2Formless, TrackType.CdMode2Form1, TrackType.CdMode2Form2] and track.raw_bytes_per_sector == 2352:
            return Cdrdao.CDRDAO_TRACK_TYPE_MODE2_RAW
        else:
            return Cdrdao.CDRDAO_TRACK_TYPE_MODE1

    def identify(self, image_filter: IFilter) -> bool:
        try:
            image_filter.get_data_fork_stream().seek(0)
            test_array = bytearray(512)
            image_filter.get_data_fork_stream().readinto(test_array)
            image_filter.get_data_fork_stream().seek(0)

            # Check for unexpected control characters
            two_consecutive_nulls = False

            for i, byte in enumerate(test_array):
                if i >= image_filter.length:
                    break

                if byte == 0:
                    if two_consecutive_nulls:
                        return False
                    two_consecutive_nulls = True
                else:
                    two_consecutive_nulls = False

                if byte < 0x20 and byte not in (0x0A, 0x0D, 0x00):
                    return False

            self._cue_stream = io.TextIOWrapper(image_filter.get_data_fork_stream(), encoding='utf-8')
            
            cr = re.compile(self.REGEX_COMMENT)
            dr = re.compile(self.REGEX_DISCTYPE)

            while self._cue_stream.peek() >= 0:
                line = self._cue_stream.readline()

                dm = dr.match(line or "")
                cm = cr.match(line or "")

                # Skip comments at start of file
                if cm:
                    continue

                return bool(dm)

            return False

        except Exception as ex:
            logger.error(f"Exception trying to identify image file: {image_filter.filename}")
            logger.exception(ex)
            return False

    def open(self, image_filter: IFilter) -> ErrorNumber:
        if image_filter is None:
            return ErrorNumber.NoSuchFile

        self._cdrdao_filter = image_filter

        try:
            image_filter.get_data_fork_stream().seek(0)
            self._cue_stream = io.TextIOWrapper(image_filter.get_data_fork_stream(), encoding='utf-8')
            in_track = False

            # Initialize all RegExs
            regex_comment = re.compile(self.REGEX_COMMENT)
            regex_disk_type = re.compile(self.REGEX_DISCTYPE)
            regex_mcn = re.compile(self.REGEX_MCN)
            regex_track = re.compile(self.REGEX_TRACK)
            regex_copy = re.compile(self.REGEX_COPY)
            regex_emphasis = re.compile(self.REGEX_EMPHASIS)
            regex_stereo = re.compile(self.REGEX_STEREO)
            regex_isrc = re.compile(self.REGEX_ISRC)
            regex_index = re.compile(self.REGEX_INDEX)
            regex_pregap = re.compile(self.REGEX_PREGAP)
            regex_zero_pregap = re.compile(self.REGEX_ZERO_PREGAP)
            regex_zero_data = re.compile(self.REGEX_ZERO_DATA)
            regex_zero_audio = re.compile(self.REGEX_ZERO_AUDIO)
            regex_audio_file = re.compile(self.REGEX_FILE_AUDIO)
            regex_file = re.compile(self.REGEX_FILE_DATA)
            regex_title = re.compile(self.REGEX_TITLE)
            regex_performer = re.compile(self.REGEX_PERFORMER)
            regex_songwriter = re.compile(self.REGEX_SONGWRITER)
            regex_composer = re.compile(self.REGEX_COMPOSER)
            regex_arranger = re.compile(self.REGEX_ARRANGER)
            regex_message = re.compile(self.REGEX_MESSAGE)
            regex_disc_id = re.compile(self.REGEX_DISC_ID)
            regex_upc = re.compile(self.REGEX_UPC)

            # Initialize disc
            self._discimage = CdrdaoDisc(tracks=[], comment="")

            current_track = CdrdaoTrack()
            current_track_number = 0
            current_track.indexes = {}
            current_track.pregap = 0
            current_sector = 0
            next_index = 2
            comment_builder = []

            line_number = 0

        while self._cue_stream.peek() >= 0:
            line_number += 1
            line = self._cue_stream.readline().strip()

            match_comment = regex_comment.match(line)
            match_disk_type = regex_disk_type.match(line)
            match_mcn = regex_mcn.match(line)
            match_track = regex_track.match(line)
            match_copy = regex_copy.match(line)
            match_emphasis = regex_emphasis.match(line)
            match_stereo = regex_stereo.match(line)
            match_isrc = regex_isrc.match(line)
            match_index = regex_index.match(line)
            match_pregap = regex_pregap.match(line)
            match_zero_pregap = regex_zero_pregap.match(line)
            match_zero_data = regex_zero_data.match(line)
            match_zero_audio = regex_zero_audio.match(line)
            match_audio_file = regex_audio_file.match(line)
            match_file = regex_file.match(line)
            match_title = regex_title.match(line)
            match_performer = regex_performer.match(line)
            match_songwriter = regex_songwriter.match(line)
            match_composer = regex_composer.match(line)
            match_arranger = regex_arranger.match(line)
            match_message = regex_message.match(line)
            match_disc_id = regex_disc_id.match(line)
            match_upc = regex_upc.match(line)

            if match_comment:
                if not match_comment.group("comment").startswith(" Track "):
                    logger.debug(f"Found comment '{match_comment.group('comment').strip()}' at line {line_number}")
                    comment_builder.append(match_comment.group("comment").strip())
            elif match_disk_type:
                logger.debug(f"Found '{match_disk_type.group('type')}' at line {line_number}")
                self._discimage.disktypestr = match_disk_type.group("type")
                self._discimage.disktype = {
                    "CD_DA": MediaType.CDDA,
                    "CD_ROM": MediaType.CDROM,
                    "CD_ROM_XA": MediaType.CDROMXA,
                    "CD_I": MediaType.CDI
                }.get(match_disk_type.group("type"), MediaType.CD)
            elif match_mcn:
                logger.debug(f"Found CATALOG '{match_mcn.group('catalog')}' at line {line_number}")
                self._discimage.mcn = match_mcn.group("catalog")
            elif match_track:
                if in_track:
                    current_sector += current_track.sectors
                    if current_track.pregap != current_track.sectors:
                        current_track.indexes[1] = current_track.start_sector + current_track.pregap
                    self._discimage.tracks.append(current_track)
                    current_track = CdrdaoTrack(indexes={}, pregap=0)
                    next_index = 2

                current_track_number += 1
                in_track = True
                
                subchan = match_track.group("subchan")
                logger.debug(f"Found TRACK type '{match_track.group('type')}' {'with no subchannel' if not subchan else f'subchannel {subchan}'} at line {line_number}")

                current_track.sequence = current_track_number
                current_track.start_sector = current_sector
                current_track.tracktype = match_track.group("type")
                
                if match_track.group("type") == "AUDIO":
                    current_track.bps = 2352
                elif match_track.group("type") in ["MODE1", "MODE2_FORM1"]:
                    current_track.bps = 2048
                elif match_track.group("type") == "MODE2_FORM2":
                    current_track.bps = 2324
                elif match_track.group("type") in ["MODE2", "MODE2_FORM_MIX"]:
                    current_track.bps = 2336
                else:
                    logger.error(f"Unsupported track mode: {match_track.group('type')}")
                    return ErrorNumber.NotSupported

                if subchan:
                    if subchan == "RW":
                        current_track.packedsubchannel = True
                    current_track.subchannel = True

            elif match_copy:
                logger.debug(f"Found {'NO ' if match_copy.group('no') else ''}COPY at line {line_number}")
                if in_track:
                    current_track.flag_dcp = not bool(match_copy.group("no"))
            elif match_emphasis:
                logger.debug(f"Found {'NO ' if match_emphasis.group('no') else ''}PRE_EMPHASIS at line {line_number}")
                if in_track:
                    current_track.flag_pre = not bool(match_emphasis.group("no"))
            elif match_stereo:
                logger.debug(f"Found {match_stereo.group('num')}_CHANNEL_AUDIO at line {line_number}")
                if in_track:
                    current_track.flag_4ch = match_stereo.group("num") == "FOUR"
            elif match_isrc:
                logger.debug(f"Found ISRC '{match_isrc.group('isrc')}' at line {line_number}")
                if in_track:
                    current_track.isrc = match_isrc.group("isrc")
            elif match_index:
                logger.debug(f"Found INDEX {match_index.group('address')} at line {line_number}")
                if in_track:
                    minutes, seconds, frames = map(int, match_index.group("address").split(":"))
                    index_sector = minutes * 60 * 75 + seconds * 75 + frames
                    current_track.indexes[next_index] = index_sector + current_track.pregap + current_track.start_sector
                    next_index += 1
            elif match_pregap:
                logger.debug(f"Found START {match_pregap.group('address') or ''} at line {line_number}")
                if in_track:
                    current_track.indexes[0] = current_track.start_sector
                    if match_pregap.group("address"):
                        minutes, seconds, frames = map(int, match_pregap.group("address").split(":"))
                        current_track.pregap = minutes * 60 * 75 + seconds * 75 + frames
                    else:
                        current_track.pregap = current_track.sectors
            elif match_zero_pregap:
                logger.debug(f"Found PREGAP {match_zero_pregap.group('length')} at line {line_number}")
                if in_track:
                    current_track.indexes[0] = current_track.start_sector
                    minutes, seconds, frames = map(int, match_zero_pregap.group("length").split(":"))
                    current_track.pregap = minutes * 60 * 75 + seconds * 75 + frames
            elif match_zero_data:
                logger.debug(f"Found ZERO {match_zero_data.group('length')} at line {line_number}")
            elif match_zero_audio:
                logger.debug(f"Found SILENCE {match_zero_audio.group('length')} at line {line_number}")
            elif match_audio_file or match_file:
                match = match_audio_file or match_file
                logger.debug(f"Found {'AUDIO' if match_audio_file else 'DATA'}FILE '{match.group('filename')}' at line {line_number}")
                if in_track:
                    current_track.trackfile = CdrdaoTrackFile(
                        datafilter=image_filter.get_filter(os.path.join(image_filter.parent_folder, match.group("filename"))),
                        datafile=match.group("filename"),
                        offset=int(match.group("base_offset") or 0),
                        filetype="BINARY",
                        sequence=current_track_number
                    )

                    if match.group("start"):
                        minutes, seconds, frames = map(int, match.group("start").split(":"))
                        start_sectors = minutes * 60 * 75 + seconds * 75 + frames
                        current_track.trackfile.offset += start_sectors * current_track.bps

                    if match.group("length"):
                        minutes, seconds, frames = map(int, match.group("length").split(":"))
                        current_track.sectors = minutes * 60 * 75 + seconds * 75 + frames
                    else:
                        current_track.sectors = (current_track.trackfile.datafilter.data_fork_length - current_track.trackfile.offset) // current_track.bps

            # Handle CD-Text related matches
            elif match_title:
                logger.debug(f"Found TITLE '{match_title.group('title')}' at line {line_number}")
                if in_track:
                    current_track.title = match_title.group("title")
                else:
                    self._discimage.title = match_title.group("title")
            elif match_performer:
                logger.debug(f"Found PERFORMER '{match_performer.group('performer')}' at line {line_number}")
                if in_track:
                    current_track.performer = match_performer.group("performer")
                else:
                    self._discimage.performer = match_performer.group("performer")
            elif match_songwriter:
                logger.debug(f"Found SONGWRITER '{match_songwriter.group('songwriter')}' at line {line_number}")
                if in_track:
                    current_track.songwriter = match_songwriter.group("songwriter")
                else:
                    self._discimage.songwriter = match_songwriter.group("songwriter")
            elif match_composer:
                logger.debug(f"Found COMPOSER '{match_composer.group('composer')}' at line {line_number}")
                if in_track:
                    current_track.composer = match_composer.group("composer")
                else:
                    self._discimage.composer = match_composer.group("composer")
            elif match_arranger:
                logger.debug(f"Found ARRANGER '{match_arranger.group('arranger')}' at line {line_number}")
                if in_track:
                    current_track.arranger = match_arranger.group("arranger")
                else:
                    self._discimage.arranger = match_arranger.group("arranger")
            elif match_message:
                logger.debug(f"Found MESSAGE '{match_message.group('message')}' at line {line_number}")
                if in_track:
                    current_track.message = match_message.group("message")
                else:
                    self._discimage.message = match_message.group("message")
            elif match_disc_id:
                logger.debug(f"Found DISC_ID '{match_disc_id.group('discid')}' at line {line_number}")
                if not in_track:
                    self._discimage.disk_id = match_disc_id.group("discid")
            elif match_upc:
                logger.debug(f"Found UPC_EAN '{match_upc.group('catalog')}' at line {line_number}")
                if not in_track:
                    self._discimage.barcode = match_upc.group("catalog")
            elif line == "":
                pass  # Ignore empty lines
            else:
                logger.warning(f"Unknown line at {line_number}: {line}")

        # Add the last track if we were processing one
        if in_track:
            if current_track.pregap != current_track.sectors:
                current_track.indexes[1] = current_track.start_sector + current_track.pregap
            self._discimage.tracks.append(current_track)

        self._discimage.comment = "\n".join(comment_builder)

        # Process tracks and build offset map
        self.partitions = []
        self._offset_map = {}
        current_offset = 0
        total_sectors = 0

        for track in self._discimage.tracks:
            partition = Partition(
                description=f"Track {track.sequence}",
                size=track.sectors * track.bps,
                length=track.sectors,
                sequence=track.sequence,
                offset=current_offset,
                start=track.start_sector,
                type=track.tracktype
            )
            self.partitions.append(partition)
            self._offset_map[track.sequence] = track.start_sector
            current_offset += partition.size
            total_sectors += track.sectors


        # Handle readable sector tags
        self._image_info.readable_sector_tags.append(SectorTagType.CdTrackFlags)
        
        for track in self._discimage.tracks:
            if track.subchannel:
                if SectorTagType.CdSectorSubchannel not in self._image_info.readable_sector_tags:
                    self._image_info.readable_sector_tags.append(SectorTagType.CdSectorSubchannel)
            
            if track.tracktype != self.CDRDAO_TRACK_TYPE_AUDIO:
                tags_to_add = [
                    SectorTagType.CdSectorSync,
                    SectorTagType.CdSectorHeader,
                    SectorTagType.CdSectorSubHeader,
                    SectorTagType.CdSectorEdc
                ]
                if track.tracktype in [self.CDRDAO_TRACK_TYPE_MODE1, self.CDRDAO_TRACK_TYPE_MODE1_RAW]:
                    tags_to_add.extend([
                        SectorTagType.CdSectorEcc,
                        SectorTagType.CdSectorEccP,
                        SectorTagType.CdSectorEccQ
                    ])
                self._image_info.readable_sector_tags.extend([tag for tag in tags_to_add if tag not in self._image_info.readable_sector_tags])
            else:
                if SectorTagType.CdTrackIsrc not in self._image_info.readable_sector_tags:
                    self._image_info.readable_sector_tags.append(SectorTagType.CdTrackIsrc)

        # Determine media type
        data_tracks = sum(1 for track in self._discimage.tracks if track.tracktype != self.CDRDAO_TRACK_TYPE_AUDIO)
        audio_tracks = len(self._discimage.tracks) - data_tracks
        mode2_tracks = sum(1 for track in self._discimage.tracks if track.tracktype in [
            self.CDRDAO_TRACK_TYPE_MODE2, self.CDRDAO_TRACK_TYPE_MODE2_FORM1, 
            self.CDRDAO_TRACK_TYPE_MODE2_FORM2, self.CDRDAO_TRACK_TYPE_MODE2_MIX, 
            self.CDRDAO_TRACK_TYPE_MODE2_RAW
        ])
        
        # Create sessions
        self.sessions = [
            Session(
                sequence=1,
                start_track=min(track.sequence for track in self._discimage.tracks),
                end_track=max(track.sequence for track in self._discimage.tracks),
                start_sector=min(track.start_sector for track in self._discimage.tracks),
                end_sector=max(track.start_sector + track.sectors - 1 for track in self._discimage.tracks)
            )
        ]

        # Create tracks
        self.tracks = []
        for cdrdao_track in self._discimage.tracks:
            track = Track(
                sequence=cdrdao_track.sequence,
                start_sector=cdrdao_track.start_sector,
                end_sector=cdrdao_track.start_sector + cdrdao_track.sectors - 1,
                type=self.cdrdao_track_type_to_track_type(cdrdao_track.tracktype),
                file=cdrdao_track.trackfile.datafile,
                file_offset=cdrdao_track.trackfile.offset,
                file_type=cdrdao_track.trackfile.filetype,
                filter=cdrdao_track.trackfile.datafilter,
                indexes=cdrdao_track.indexes,
                pregap=cdrdao_track.pregap,
                session=1,
                raw_bytes_per_sector=cdrdao_track.bps,
                bytes_per_sector=self.cdrdao_track_type_to_cooked_bytes_per_sector(cdrdao_track.tracktype)
            )
            if cdrdao_track.subchannel:
                track.subchannel_file = cdrdao_track.trackfile.datafile
                track.subchannel_filter = cdrdao_track.trackfile.datafilter
                track.subchannel_type = TrackSubchannelType.PackedInterleaved if cdrdao_track.packedsubchannel else TrackSubchannelType.RawInterleaved
            else:
                track.subchannel_type = TrackSubchannelType.None_
            self.tracks.append(track)

        # Create TOC
        self._create_full_toc()
        self._image_info.readable_media_tags.append(MediaTagType.CD_FullTOC)

        # Set image info
        self._image_info.media_type = self._discimage.disktype
        self._image_info.media_type = self._determine_media_type()
        self._image_info.sectors = sum(track.sectors for track in self._discimage.tracks)
        self._image_info.sector_size = max(track.bps for track in self._discimage.tracks)
        self._image_info.image_size = sum(track.sectors * track.bps for track in self._discimage.tracks)
        self._image_info.creation_time = datetime.fromtimestamp(os.path.getctime(image_filter.base_path))
        self._image_info.last_modification_time = datetime.fromtimestamp(os.path.getmtime(image_filter.base_path))
        self._image_info.media_title = self._discimage.title
        self._image_info.comments = self._discimage.comment
        self._image_info.media_serial_number = self._discimage.mcn
        self._image_info.media_barcode = self._discimage.barcode
        self._image_info.metadata_media_type = MetadataMediaType.OpticalDisc
        self._image_info.application = "CDRDAO"

        # Handle readable media tags
        if self._discimage.mcn:
            self._image_info.readable_media_tags.append(MediaTagType.CD_MCN)
        if self._full_toc:
            self._image_info.readable_media_tags.append(MediaTagType.CD_FullTOC)


        # handle CD-Text
        if self._cdtext:
            self._parse_cd_text(self._cdtext)

        # Log debug information
        logger.debug("Disc image parsing results:")
        logger.debug(f"Disc type: {self._discimage.disktype}")
        logger.debug(f"MCN: {self._discimage.mcn}")
        logger.debug(f"Barcode: {self._discimage.barcode}")
        logger.debug(f"Disc ID: {self._discimage.disk_id}")
        logger.debug(f"Comment: {self._discimage.comment}")
        logger.debug(f"Number of tracks: {len(self._discimage.tracks)}")
        
        for i, track in enumerate(self._discimage.tracks):
            logger.debug(f"Track {track.sequence} information:")
            logger.debug(f"  Bytes per sector: {track.bps}")
            logger.debug(f"  Pregap: {track.pregap} sectors")
            logger.debug(f"  Data: {track.sectors} sectors starting at sector {track.start_sector}")
            logger.debug(f"  Type: {track.tracktype}")
            logger.debug(f"  File: {track.trackfile.datafile}")
            logger.debug(f"  File offset: {track.trackfile.offset}")
            logger.debug(f"  Subchannel: {'Yes' if track.subchannel else 'No'}")
            logger.debug(f"  Indexes: {track.indexes}")

        logger.debug("Partition map:")
        for partition in self.partitions:
            logger.debug(f"  Sequence: {partition.sequence}")
            logger.debug(f"  Type: {partition.type}")
            logger.debug(f"  Start sector: {partition.start}")
            logger.debug(f"  Sectors: {partition.length}")
            logger.debug(f"  Start offset: {partition.offset}")
            logger.debug(f"  Size in bytes: {partition.size}")

        return ErrorNumber.NoError

        except Exception as ex:
            logger.error(f"Exception trying to open image file: {image_filter.filename}")
            logger.exception(ex)
            return ErrorNumber.UnexpectedException

    def _get_sector_layout(self, track: CdrdaoTrack) -> Tuple[int, int, int]:
        sector_offset = 0
        sector_size = track.bps
        sector_skip = 0

        if track.tracktype == self.CDRDAO_TRACK_TYPE_MODE1:
            sector_offset = 16
            sector_size = 2048
            sector_skip = 288
        elif track.tracktype in [self.CDRDAO_TRACK_TYPE_MODE2, self.CDRDAO_TRACK_TYPE_MODE2_MIX]:
            sector_offset = 16
            sector_size = 2336
            sector_skip = 0

        if track.subchannel:
            sector_skip += 96

        return sector_offset, sector_size, sector_skip

    def _swap_audio_endianness(self, buffer: bytearray) -> bytearray:
        return bytearray(buffer[i+1] + buffer[i] for i in range(0, len(buffer), 2))

    def read_sector(self, sector_address: int, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        return self.read_sectors(sector_address, 1, track)
    
    def read_sectors(self, sector_address: int, length: int, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        if track is None:
            for track_sequence, start_sector in self._offset_map.items():
                if sector_address >= start_sector:
                    track = next((t for t in self._discimage.tracks if t.sequence == track_sequence), None)
                    if track and sector_address - start_sector < track.sectors:
                        return self.read_sectors(sector_address - start_sector, length, track_sequence)
            return ErrorNumber.SectorNotFound, None
    
        cdrdao_track = next((t for t in self._discimage.tracks if t.sequence == track), None)
        if cdrdao_track is None:
            return ErrorNumber.SectorNotFound, None
    
        if sector_address + length > cdrdao_track.sectors:
            return ErrorNumber.OutOfRange, None
    
        sector_offset, sector_size, sector_skip = self._get_sector_layout(cdrdao_track)
        
        buffer = bytearray(sector_size * length)
        
        with cdrdao_track.trackfile.datafilter.get_data_fork_stream() as stream:
            stream.seek(cdrdao_track.trackfile.offset + (sector_address * (sector_offset + sector_size + sector_skip)))
            
            if cdrdao_track.tracktype in [self.CDRDAO_TRACK_TYPE_MODE2, self.CDRDAO_TRACK_TYPE_MODE2_MIX, self.CDRDAO_TRACK_TYPE_MODE2_RAW]:
                temp_buffer = bytearray((sector_size + sector_skip) * length)
                stream.readinto(temp_buffer)
                for i in range(length):
                    sector = temp_buffer[i*(sector_size + sector_skip):i*(sector_size + sector_skip) + sector_size]
                    buffer[i*sector_size:(i+1)*sector_size] = Sector.get_user_data_from_mode2(sector)
            elif sector_offset == 0 and sector_skip == 0:
                stream.readinto(buffer)
            else:
                for i in range(length):
                    stream.seek(sector_offset, io.SEEK_CUR)
                    stream.readinto(buffer[i*sector_size:(i+1)*sector_size])
                    stream.seek(sector_skip, io.SEEK_CUR)
    
        if cdrdao_track.tracktype == self.CDRDAO_TRACK_TYPE_AUDIO:
            buffer = self._swap_audio_endianness(buffer)
    
        return ErrorNumber.NoError, bytes(buffer)

    def read_sector_long(self, sector_address: int, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        return self.read_sectors_long(sector_address, 1, track)
    
    def read_sectors_long(self, sector_address: int, length: int, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        if track is None:
            for track_sequence, start_sector in self._offset_map.items():
                if sector_address >= start_sector:
                    track = next((t for t in self._discimage.tracks if t.sequence == track_sequence), None)
                    if track and sector_address - start_sector < track.sectors:
                        return self.read_sectors_long(sector_address - start_sector, length, track_sequence)
            return ErrorNumber.SectorNotFound, None
    
        cdrdao_track = next((t for t in self._discimage.tracks if t.sequence == track), None)
        if cdrdao_track is None:
            return ErrorNumber.SectorNotFound, None
    
        if length > cdrdao_track.sectors:
            return ErrorNumber.OutOfRange, None
    
        sector_size = 2352
        sector_skip = 96 if cdrdao_track.subchannel else 0
    
        buffer = bytearray((sector_size + sector_skip) * length)
    
        with cdrdao_track.trackfile.datafilter.get_data_fork_stream() as stream:
            stream.seek(cdrdao_track.trackfile.offset + (sector_address * (sector_size + sector_skip)))
            stream.readinto(buffer)
    
        if cdrdao_track.tracktype == self.CDRDAO_TRACK_TYPE_AUDIO:
            # Swap endianness for audio tracks
            buffer = self._swap_audio_endianness(buffer)
    
        return ErrorNumber.NoError, bytes(buffer[:sector_size * length])
    
    def read_sector_tag(self, sector_address: int, tag: SectorTagType, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        return self.read_sectors_tag(sector_address, 1, tag, track)

    def _get_tag_layout(self, track: CdrdaoTrack, tag: SectorTagType) -> Tuple[int, int, int]:
        sector_offset = 0
        sector_size = 0
        sector_skip = 0

        if track.tracktype == self.CDRDAO_TRACK_TYPE_MODE1:
            if tag == SectorTagType.CdSectorSync:
                sector_offset, sector_size, sector_skip = 0, 12, 2340
            elif tag == SectorTagType.CdSectorHeader:
                sector_offset, sector_size, sector_skip = 12, 4, 2336
            elif tag == SectorTagType.CdSectorSubHeader:
                raise ValueError("Unsupported tag type for Mode 1")
            elif tag == SectorTagType.CdSectorEcc:
                sector_offset, sector_size, sector_skip = 2076, 276, 0
            elif tag == SectorTagType.CdSectorEccP:
                sector_offset, sector_size, sector_skip = 2076, 172, 104
            elif tag == SectorTagType.CdSectorEccQ:
                sector_offset, sector_size, sector_skip = 2248, 104, 0
            elif tag == SectorTagType.CdSectorEdc:
                sector_offset, sector_size, sector_skip = 2064, 4, 284
            else:
                raise ValueError("Unsupported tag type for Mode 1")
        elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_FORMLESS:
            if tag in [SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader, 
                       SectorTagType.CdSectorEcc, SectorTagType.CdSectorEccP, SectorTagType.CdSectorEccQ]:
                raise ValueError("Unsupported tag type for Mode 2 Formless")
            elif tag == SectorTagType.CdSectorSubHeader:
                sector_offset, sector_size, sector_skip = 0, 8, 2328
            elif tag == SectorTagType.CdSectorEdc:
                sector_offset, sector_size, sector_skip = 2332, 4, 0
            else:
                raise ValueError("Unsupported tag type for Mode 2 Formless")
        elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_FORM1:
            if tag == SectorTagType.CdSectorSync:
                sector_offset, sector_size, sector_skip = 0, 12, 2340
            elif tag == SectorTagType.CdSectorHeader:
                sector_offset, sector_size, sector_skip = 12, 4, 2336
            elif tag == SectorTagType.CdSectorSubHeader:
                sector_offset, sector_size, sector_skip = 16, 8, 2328
            elif tag == SectorTagType.CdSectorEcc:
                sector_offset, sector_size, sector_skip = 2076, 276, 0
            elif tag == SectorTagType.CdSectorEccP:
                sector_offset, sector_size, sector_skip = 2076, 172, 104
            elif tag == SectorTagType.CdSectorEccQ:
                sector_offset, sector_size, sector_skip = 2248, 104, 0
            elif tag == SectorTagType.CdSectorEdc:
                sector_offset, sector_size, sector_skip = 2072, 4, 276
            else:
                raise ValueError("Unsupported tag type for Mode 2 Form 1")
        elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_FORM2:
            if tag == SectorTagType.CdSectorSync:
                sector_offset, sector_size, sector_skip = 0, 12, 2340
            elif tag == SectorTagType.CdSectorHeader:
                sector_offset, sector_size, sector_skip = 12, 4, 2336
            elif tag == SectorTagType.CdSectorSubHeader:
                sector_offset, sector_size, sector_skip = 16, 8, 2328
            elif tag == SectorTagType.CdSectorEdc:
                sector_offset, sector_size, sector_skip = 2348, 4, 0
            else:
                raise ValueError("Unsupported tag type for Mode 2 Form 2")

        if sector_size == 0:
            raise ValueError(f"Unsupported tag type {tag} for track type {track.tracktype}")

        return sector_offset, sector_size, sector_skip

    def read_sectors_tag(self, sector_address: int, length: int, tag: SectorTagType, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        if track is None:
            for track_sequence, start_sector in self._offset_map.items():
                if sector_address >= start_sector:
                    track = next((t for t in self._discimage.tracks if t.sequence == track_sequence), None)
                    if track and sector_address - start_sector < track.sectors:
                        return self.read_sectors_tag(sector_address - start_sector, length, tag, track_sequence)
            return ErrorNumber.SectorNotFound, None
    
        cdrdao_track = next((t for t in self._discimage.tracks if t.sequence == track), None)
        if cdrdao_track is None:
            return ErrorNumber.SectorNotFound, None
    
        if sector_address + length > cdrdao_track.sectors:
            return ErrorNumber.OutOfRange, None
    
        if cdrdao_track.tracktype == self.CDRDAO_TRACK_TYPE_AUDIO and tag not in [SectorTagType.CdTrackFlags, SectorTagType.CdTrackIsrc, SectorTagType.CdSectorSubchannel]:
            return ErrorNumber.NotSupported, None
    
        if tag == SectorTagType.CdTrackFlags:
            return self._read_track_flags(cdrdao_track)
        elif tag == SectorTagType.CdTrackIsrc:
            return self._read_track_isrc(cdrdao_track)
        elif tag == SectorTagType.CdSectorSubchannel:
            return self._read_subchannel(cdrdao_track, sector_address, length)

        try:
            sector_offset, sector_size, sector_skip = self._get_tag_layout(cdrdao_track, tag)
        except ValueError:
            return ErrorNumber.NotSupported, None
    
        if sector_size == 0:
            return ErrorNumber.NotSupported, None
    
        buffer = bytearray(sector_size * length)
        with cdrdao_track.trackfile.datafilter.get_data_fork_stream() as stream:
            stream.seek(cdrdao_track.trackfile.offset + (sector_address * 2352))
            
            if sector_offset == 0 and sector_skip == 0:
                stream.readinto(buffer)
            else:
                for i in range(length):
                    stream.seek(sector_offset, io.SEEK_CUR)
                    stream.readinto(buffer[i*sector_size:(i+1)*sector_size])
                    stream.seek(sector_skip, io.SEEK_CUR)
    
        return ErrorNumber.NoError, bytes(buffer)

    def _read_track_flags(self, track: CdrdaoTrack) -> Tuple[ErrorNumber, Optional[bytes]]:
        flags = 0
        if track.tracktype != self.CDRDAO_TRACK_TYPE_AUDIO:
            flags |= 0x04  # Data track
        if track.flag_dcp:
            flags |= 0x02  # Digital copy permitted
        if track.flag_4ch:
            flags |= 0x08  # Four channel audio
        if track.flag_pre:
            flags |= 0x01  # Pre-emphasis
        return ErrorNumber.NoError, bytes([flags])
    
    def _read_track_isrc(self, track: CdrdaoTrack) -> Tuple[ErrorNumber, Optional[bytes]]:
        if track.isrc:
            return ErrorNumber.NoError, track.isrc.encode('ascii')
        return ErrorNumber.NoData, None
    
    def _read_subchannel(self, track: CdrdaoTrack, sector_address: int, length: int) -> Tuple[ErrorNumber, Optional[bytes]]:
        if not track.subchannel:
            return ErrorNumber.NotSupported, None
        
        buffer = bytearray(96 * length)
        with track.trackfile.datafilter.get_data_fork_stream() as stream:
            stream.seek(track.trackfile.offset + (sector_address * (2352 + 96)) + 2352)
            stream.readinto(buffer)
        return ErrorNumber.NoError, bytes(buffer)

    def verify_sector(self, sector_address: int) -> Optional[bool]:
        error, buffer = self.read_sector_long(sector_address)
        if error != ErrorNumber.NoError:
            return None
        return CdChecksums.check_cd_sector(buffer)

    def verify_sectors(self, sector_address: int, length: int) -> Tuple[Optional[bool], List[int], List[int]]:
        failing_lbas = []
        unknown_lbas = []
        error, buffer = self.read_sectors_long(sector_address, length)

        if error != ErrorNumber.NoError:
            return None, failing_lbas, unknown_lbas

        sector_size = len(buffer) // length
        for i in range(length):
            sector = buffer[i * sector_size : (i + 1) * sector_size]
            sector_status = CdChecksums.check_cd_sector(sector)

            if sector_status is None:
                unknown_lbas.append(sector_address + i)
            elif sector_status is False:
                failing_lbas.append(sector_address + i)

        if unknown_lbas:
            return None, failing_lbas, unknown_lbas
        return len(failing_lbas) == 0, failing_lbas, unknown_lbas

    def get_session_tracks(self, session: Union[Session, int]) -> List[Track]:
        """
        Retrieves a list of tracks for a given session.
        This method is provided for compatibility with multi-session CD operations
        and may be used by other parts of the Aaru system.

        :param session: Either a Session object or a session number
        :return: A list of Track objects belonging to the specified session
        """
        if isinstance(session, Session):
            return self.get_session_tracks(session.sequence)
        return [track for track in self.tracks if track.session == session]

    # need to check if this really belongs here
    def read_media_tag(self, tag: MediaTagType) -> Tuple[ErrorNumber, Optional[bytes]]:
        if tag == MediaTagType.CD_MCN:
            if self._discimage.mcn:
                return ErrorNumber.NoError, self._discimage.mcn.encode('ascii')
            else:
                return ErrorNumber.NoData, None
        elif tag == MediaTagType.CD_FullTOC:
            if self._full_toc:
                return ErrorNumber.NoError, self._full_toc
            else:
                return ErrorNumber.NoData, None
        else:
            return ErrorNumber.NotSupported, None
