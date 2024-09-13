import io
import re
import os
from datetime import datetime
from typing import List, Dict, Optional
import logging

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

    def read_sector(self, *args, **kwargs):
        return self.reader.read_sector(*args, **kwargs)

    def read_sectors(self, *args, **kwargs):
        return self.reader.read_sectors(*args, **kwargs)

    def read_sector_long(self, *args, **kwargs):
        return self.reader.read_sector_long(*args, **kwargs)

    def read_sectors_long(self, *args, **kwargs):
        return self.reader.read_sectors_long(*args, **kwargs)

    def read_sector_tag(self, *args, **kwargs):
        return self.reader.read_sector_tag(*args, **kwargs)

    def read_sectors_tag(self, *args, **kwargs):
        return self.reader.read_sectors_tag(*args, **kwargs)

    def read_media_tag(self, *args, **kwargs):
        return self.reader.read_media_tag(*args, **kwargs)

    def verify_sector(self, *args, **kwargs):
        return self.reader.verify_sector(*args, **kwargs)

    def verify_sectors(self, *args, **kwargs):
        return self.reader.verify_sectors(*args, **kwargs)

    def get_session_tracks(self, *args, **kwargs):
        return self.reader.get_session_tracks(*args, **kwargs)

    def open(self, image_filter: IFilter) -> ErrorNumber:

        def _process_track_gaps(self, current_track: CdrdaoTrack, next_track: Optional[CdrdaoTrack]):
            if current_track.pregap > 0:
                current_track.start_sector -= current_track.pregap
                current_track.sectors += current_track.pregap
            
            if next_track and next_track.start_sector > current_track.start_sector + current_track.sectors:
                current_track.postgap = next_track.start_sector - (current_track.start_sector + current_track.sectors)
                current_track.sectors += current_track.postgap

        def _process_track_indexes(self, current_track: CdrdaoTrack, current_sector: int):
            if 0 not in current_track.indexes:
                current_track.indexes[0] = current_track.start_sector
            
            if 1 not in current_track.indexes and current_track.pregap != current_track.sectors:
                current_track.indexes[1] = current_track.start_sector + current_track.pregap
            
            for index, sector in current_track.indexes.items():
                if index > 1:
                    current_track.indexes[index] = sector + current_track.start_sector
        
            # Ensure indexes are properly ordered
            current_track.indexes = dict(sorted(current_track.indexes.items()))

        def _detect_track_type(self, track: CdrdaoTrack) -> TrackType:
            for s in range(225, min(750, track.sectors)):
                sync_test = bytearray(12)
                sect_test = bytearray(2352)
        
                pos = track.trackfile.offset + s * 2352
        
                with track.trackfile.datafilter.get_data_fork_stream() as stream:
                    if pos >= stream.seek(0, io.SEEK_END):
                        break
        
                    stream.seek(pos)
                    stream.readinto(sect_test)
                    sync_test[:] = sect_test[:12]
        
                if sync_test != Sector.SYNC_MARK:
                    continue
        
                if self._scrambled:
                    sect_test = Sector.scramble(sect_test)
        
                if sect_test[15] == 1:
                    track.bps = 2048
                    self._update_readable_sector_tags([
                        SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader,
                        SectorTagType.CdSectorEcc, SectorTagType.CdSectorEccP,
                        SectorTagType.CdSectorEccQ, SectorTagType.CdSectorEdc
                    ])
                    return TrackType.CdMode1
        
                if sect_test[15] == 2:
                    sub_hdr1 = sect_test[16:20]
                    sub_hdr2 = sect_test[20:24]
                    emp_hdr = bytes(4)
        
                    if sub_hdr1 == sub_hdr2 and sub_hdr1 != emp_hdr:
                        if sub_hdr1[2] & 0x20:
                            track.bps = 2324
                            self._update_readable_sector_tags([
                                SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader,
                                SectorTagType.CdSectorSubHeader, SectorTagType.CdSectorEdc
                            ])
                            return TrackType.CdMode2Form2
                        else:
                            track.bps = 2048
                            self._update_readable_sector_tags([
                                SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader,
                                SectorTagType.CdSectorSubHeader, SectorTagType.CdSectorEcc,
                                SectorTagType.CdSectorEccP, SectorTagType.CdSectorEccQ,
                                SectorTagType.CdSectorEdc
                            ])
                            return TrackType.CdMode2Form1
        
                    track.bps = 2336
                    self._update_readable_sector_tags([
                        SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader
                    ])
                    return TrackType.CdMode2Formless
        
            return TrackType.Data  # Default to Data if no specific type is detected

        def _cdrdao_track_to_track(self, cdrdao_track: CdrdaoTrack) -> Track:
            return Track(
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
                session=1,  # Assuming single session for now
                raw_bytes_per_sector=cdrdao_track.bps,
                bytes_per_sector=self.cdrdao_track_type_to_cooked_bytes_per_sector(cdrdao_track.tracktype),
                subchannel_file=cdrdao_track.trackfile.datafile if cdrdao_track.subchannel else None,
                subchannel_filter=cdrdao_track.trackfile.datafilter if cdrdao_track.subchannel else None,
                subchannel_type=TrackSubchannelType.PackedInterleaved if cdrdao_track.packedsubchannel else TrackSubchannelType.RawInterleaved if cdrdao_track.subchannel else TrackSubchannelType.None_
            )
        
        def _update_readable_sector_tags(self, tags):
            for tag in tags:
                if tag not in self._image_info.readable_sector_tags:
                    self._image_info.readable_sector_tags.append(tag)

        if image_filter is None:
            return ErrorNumber.NoSuchFile

        self._cdrdao_filter = image_filter

        try:
            image_filter.get_data_fork_stream().seek(0)
            self._cue_stream = io.TextIOWrapper(image_filter.get_data_fork_stream(), encoding='utf-8')
            in_track = False
            current_track = None
            current_track_number = 0
            current_sector = 0
            line_number = 0

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
            regex_disc_scrambled = re.compile(self.REGEX_DISC_SCRAMBLED)

            # Initialize disc
            self._discimage = CdrdaoDisc(tracks=[], comment="")

            comment_builder = []
    
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
                match_disc_scrambled = regex_disc_scrambled.match(line)
                
                # cd text matches
                match_title = regex_title.match(line)
                match_performer = regex_performer.match(line)
                match_songwriter = regex_songwriter.match(line)
                match_composer = regex_composer.match(line)
                match_arranger = regex_arranger.match(line)
                match_message = regex_message.match(line)
                match_disc_id = regex_disc_id.match(line)
                match_upc = regex_upc.match(line)

                if match_track:
                    if in_track:
                        self._process_track_gaps(current_track, None)  # Process gaps for the previous track
                        self._process_track_indexes(current_track, current_sector)
                        current_sector += current_track.sectors
                        self._discimage.tracks.append(current_track)
       
                    current_track_number += 1
                    current_track = CdrdaoTrack(
                        sequence=current_track_number,
                        start_sector=current_sector,
                        tracktype=match_track.group("type"),
                        bps=2352 if match_track.group("type") == "AUDIO" else 2048,
                        subchannel=bool(match_track.group("subchan")),
                        packedsubchannel=match_track.group("subchan") == "RW"
                        indexes={},
                        pregap=0
                    )
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
                elif match_comment:
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
                elif match_copy and current_track:
                    logger.debug(f"Found {'NO ' if match_copy.group('no') else ''}COPY at line {line_number}")
                    current_track.flag_dcp = not bool(match_copy.group("no"))
                elif match_emphasis and current_track:
                    logger.debug(f"Found {'NO ' if match_emphasis.group('no') else ''}PRE_EMPHASIS at line {line_number}")
                    current_track.flag_pre = not bool(match_emphasis.group("no"))
                elif match_stereo and current_track:
                    logger.debug(f"Found {match_stereo.group('num')}_CHANNEL_AUDIO at line {line_number}")
                    current_track.flag_4ch = match_stereo.group("num") == "FOUR"
                elif match_isrc and current_track:
                    logger.debug(f"Found ISRC '{match_isrc.group('isrc')}' at line {line_number}")
                    current_track.isrc = match_isrc.group("isrc")
                elif match_index and current_track:
                    logger.debug(f"Found INDEX {match_index.group('address')} at line {line_number}")
                    minutes, seconds, frames = map(int, match_index.group("address").split(":"))
                    index_sector = minutes * 60 * 75 + seconds * 75 + frames
                    current_track.indexes[next_index] = index_sector + current_track.pregap + current_track.start_sector
                    next_index += 1
                elif match_pregap and current_track:
                    logger.debug(f"Found START {match_pregap.group('address') or ''} at line {line_number}")
                    current_track.indexes[0] = current_track.start_sector
                    if match_pregap.group("address"):
                        minutes, seconds, frames = map(int, match_pregap.group("address").split(":"))
                        current_track.pregap = minutes * 60 * 75 + seconds * 75 + frames
                    else:
                        current_track.pregap = current_track.sectors
                elif match_zero_pregap and current_track:
                    logger.debug(f"Found PREGAP {match_zero_pregap.group('length')} at line {line_number}")
                    current_track.indexes[0] = current_track.start_sector
                    minutes, seconds, frames = map(int, match_zero_pregap.group("length").split(":"))
                    current_track.pregap = minutes * 60 * 75 + seconds * 75 + frames
                elif match_zero_data:
                    logger.debug(f"Found ZERO {match_zero_data.group('length')} at line {line_number}")
                elif match_zero_audio:
                    logger.debug(f"Found SILENCE {match_zero_audio.group('length')} at line {line_number}")
                elif (match_audio_file or match_file) and current_track:
                    match = match_audio_file or match_file
                    logger.debug(f"Found {'AUDIO' if match_audio_file else 'DATA'}FILE '{match.group('filename')}' at line {line_number}")
                    current_track.trackfile = CdrdaoTrackFile(
                        datafilter=image_filter.get_filter(os.path.join(image_filter.parent_folder, match.group("filename"))),
                        datafile=match.group("filename"),
                        offset=int(match.group("base_offset") or 0),
                        filetype="BINARY",
                        sequence=current_track_number
                    )
                    start_sectors = 0
                    if match.group("start"):
                        minutes, seconds, frames = map(int, match.group("start").split(":"))
                        start_sectors = minutes * 60 * 75 + seconds * 75 + frames
                        current_track.trackfile.offset += start_sectors * current_track.bps

                    if match.group("length"):
                        minutes, seconds, frames = map(int, match.group("length").split(":"))
                        current_track.sectors = minutes * 60 * 75 + seconds * 75 + frames
                    else:
                        current_track.sectors = (current_track.trackfile.datafilter.data_fork_length - current_track.trackfile.offset) // current_track.bps
                    
                    current_sector += start_sectors + current_track.sectors
                elif match_disc_scrambled:
                    logger.debug(f"Found DataTracksScrambled {match_disc_scrambled.group('value')} at line {line_number}")
                    self._scrambled |= match_disc_scrambled.group('value') == "1"
                elif match_audio_file or match_file:
                    if not in_track:
                        return ErrorNumber.InvalidData  # File declaration outside of track


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
                self._process_track_gaps(current_track, None)
                self._process_track_indexes(current_track, current_sector)
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
                track.type = self._detect_track_type(track)

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
            self.tracks = [self._cdrdao_track_to_track(ct) for ct in self._discimage.tracks]

            # Create TOC
            self._create_full_toc()
            self._image_info.readable_media_tags.append(MediaTagType.CD_FullTOC)

            # Set image info
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
