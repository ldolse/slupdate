import io
import struct
import re
import os
from datetime import datetime
from typing import List, Dict, Optional, BinaryIO
from modules.ifilter import IFilter
from modules.cdrdao_filter import CDRDAOFilter

from modules.CD.atip import ATIP

from modules.CD.subchannel import Subchannel
from modules.CD.cd_types import (
    TrackType, TrackSubchannelType, SectorTagType, MediaType, 
    MediaTagType, MetadataMediaType, TocControl,
    Track, Session, Partition, ImageInfo, enum_name
)
from modules.CD.fulltoc import FullTOC, TrackDataDescriptor, CDFullTOC
from modules.error_number import ErrorNumber

from .utilities import *
from .constants import *
from .properties import *
from .read import CdrdaoRead
from .structs import CdrdaoTrackFile, CdrdaoTrack, CdrdaoDisc
from .write import *

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Cdrdao(CdrdaoProperties):
    MODULE_NAME = "CDRDAO plugin"

    def __init__(self, path: str):
        self._cdrdao_filter: Optional[CDRDAOFilter] = None
        self._bin_stream: Optional[BinaryIO] = None
        self._toc_stream = None
        self._path = path  # Store the path as an instance variable
        self.reader = CdrdaoRead(self)
        self._catalog: Optional[str] = None
        self._cdtext: Optional[bytes] = None
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

    def read_sector_tag(self, *args, **kwargs):
        return self.reader.read_sector_tag(*args, **kwargs)

    def update_reader(self):
        self.reader.update(self._discimage, self._offset_map, self._data_stream, self._scrambled)

    def open(self, image_filter: IFilter) -> ErrorNumber:
        if image_filter is None:
            return ErrorNumber.NoSuchFile
        
        self._cdrdao_filter = image_filter

        if image_filter is None:
            return ErrorNumber.NoSuchFile

        self._cdrdao_filter = image_filter
        toc_path = self._cdrdao_filter.path

        try:
            with open(toc_path, 'r', encoding='utf-8') as toc_file:
                bin_file = None
                for line in toc_file:
                    if line.strip().startswith("DATAFILE"):
                        bin_file = line.split('"')[1]
                        break
                
                if not bin_file:
                    logger.error("No DATAFILE found in TOC")
                    return ErrorNumber.FileNotFound

                bin_path = os.path.join(os.path.dirname(self._cdrdao_filter.path), bin_file)
                self._cdrdao_filter.get_filter(bin_path)
                self._bin_stream = self._cdrdao_filter.get_bin_stream()

                if not self._bin_stream:
                    logger.error(f"Binary file not found: {bin_path}")
                    return ErrorNumber.FileNotFound

            # Process the .toc file
            with open(toc_path, 'r', encoding='utf-8') as toc_file:
                in_track = False
                current_track = None
                current_track_number = 0
                current_sector = 0
                line_number = 0

                # Initialize all RegExs
                regex_comment = re.compile(REGEX_COMMENT)
                regex_disk_type = re.compile(REGEX_DISCTYPE)
                regex_mcn = re.compile(REGEX_MCN)
                regex_track = re.compile(REGEX_TRACK)
                regex_copy = re.compile(REGEX_COPY)
                regex_emphasis = re.compile(REGEX_EMPHASIS)
                regex_stereo = re.compile(REGEX_STEREO)
                regex_isrc = re.compile(REGEX_ISRC)
                regex_index = re.compile(REGEX_INDEX)
                regex_pregap = re.compile(REGEX_PREGAP)
                regex_zero_pregap = re.compile(REGEX_ZERO_PREGAP)
                regex_zero_data = re.compile(REGEX_ZERO_DATA)
                regex_zero_audio = re.compile(REGEX_ZERO_AUDIO)
                regex_audio_file = re.compile(REGEX_FILE_AUDIO)
                regex_file = re.compile(REGEX_FILE_DATA)
                regex_title = re.compile(REGEX_TITLE)
                regex_performer = re.compile(REGEX_PERFORMER)
                regex_songwriter = re.compile(REGEX_SONGWRITER)
                regex_composer = re.compile(REGEX_COMPOSER)
                regex_arranger = re.compile(REGEX_ARRANGER)
                regex_message = re.compile(REGEX_MESSAGE)
                regex_disc_id = re.compile(REGEX_DISC_ID)
                regex_upc = re.compile(REGEX_UPC)
                regex_disc_scrambled = re.compile(REGEX_DISC_SCRAMBLED)

                # Initialize disc
                self._discimage = CdrdaoDisc(tracks=[], comment="")

                comment_builder = []
        
                for line in toc_file:
                    line_number += 1
                    line = line.strip()
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
                            process_track_gaps(current_track, None)  # Process gaps for the previous track
                            process_track_indexes(current_track, current_sector)
                            current_sector += current_track.sectors
                            self._discimage.tracks.append(current_track)
        
                        current_track_number += 1
                        current_track = CdrdaoTrack(
                            sequence=current_track_number,
                            start_sector=current_sector,
                            tracktype=match_track.group("type"),
                            bytes_per_sector=2352 if match_track.group("type") == "AUDIO" else 2048,
                            subchannel=bool(match_track.group("subchan")),
                            packedsubchannel=match_track.group("subchan") == "RW",
                            indexes={},
                            pregap=0
                        )
                        in_track = True              
                        subchan = match_track.group("subchan")
                        logger.debug(f"Found TRACK type '{match_track.group('type')}' {'with no subchannel' if not subchan else f'subchannel {subchan}'} at line {line_number}")
        
                        current_track.sequence = current_track_number
                        current_track.start_sector = current_sector
                        current_track.tracktype = match_track.group("type")
                        
                        # Adjust bytes_per_sector based on track type
                        if current_track.tracktype == "AUDIO":
                            current_track.bps = 2352
                        elif current_track.tracktype in ["MODE1", "MODE2_FORM1"]:
                            current_track.bps = 2048
                        elif current_track.tracktype == "MODE2_FORM2":
                            current_track.bps = 2324
                        elif current_track.tracktype in ["MODE2", "MODE2_FORM_MIX", "MODE2_RAW"]:
                            current_track.bps = 2336
                        else:
                            logger.warning(f"Unknown track mode: {current_track.tracktype}, defaulting to 2352 bytes per sector")
        
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
                        if match_audio_file and match.groupdict().get("start"):
                            minutes, seconds, frames = map(int, match.group("start").split(":"))
                            start_sectors = minutes * 60 * 75 + seconds * 75 + frames
                            current_track.trackfile.offset += start_sectors * current_track.bytes_per_sector

                        if match.groupdict().get("length"):
                            minutes, seconds, frames = map(int, match.group("length").split(":"))
                            current_track.sectors = minutes * 60 * 75 + seconds * 75 + frames
                        else:
                            current_track.sectors = (current_track.trackfile.datafilter.data_fork_length - current_track.trackfile.offset) // current_track.bytes_per_sector
                        
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
                    process_track_gaps(current_track, None)
                    process_track_indexes(current_track, current_sector)
                    self._discimage.tracks.append(current_track)
            
                self._discimage.comment = "\n".join(comment_builder)

            # Open the binary .bin file
            self._data_stream = open(bin_path, 'rb')

            # Process tracks and build offset map
            self.partitions = []
            self._offset_map = {}
            current_offset = 0
            total_sectors = 0

            for track in self._discimage.tracks:
                partition = Partition(
                    description=f"Track {track.sequence}",
                    size=track.sectors * track.bytes_per_sector,
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
            
                if track.tracktype != CDRDAO_TRACK_TYPE_AUDIO:
                    tags_to_add = [
                        SectorTagType.CdSectorSync,
                        SectorTagType.CdSectorHeader,
                        SectorTagType.CdSectorSubHeader,
                        SectorTagType.CdSectorEdc
                    ]
                    if track.tracktype in [CDRDAO_TRACK_TYPE_MODE1, CDRDAO_TRACK_TYPE_MODE1_RAW]:
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
            data_tracks = sum(1 for track in self._discimage.tracks if track.tracktype != CDRDAO_TRACK_TYPE_AUDIO)
            audio_tracks = len(self._discimage.tracks) - data_tracks
            mode2_tracks = sum(1 for track in self._discimage.tracks if track.tracktype in [
                CDRDAO_TRACK_TYPE_MODE2, CDRDAO_TRACK_TYPE_MODE2_FORM1, 
                CDRDAO_TRACK_TYPE_MODE2_FORM2, CDRDAO_TRACK_TYPE_MODE2_MIX, 
                CDRDAO_TRACK_TYPE_MODE2_RAW
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
            self.tracks = [cdrdao_track_to_track(ct) for ct in self._discimage.tracks]

            # Create TOC
            self._create_full_toc()
            self._image_info.readable_media_tags.append(MediaTagType.CD_FullTOC)

            # Set image info
            self._image_info.media_type = determine_media_type(self._discimage.tracks,self.sessions)
            self._image_info.sectors = sum(track.sectors for track in self._discimage.tracks)
            self._image_info.sector_size = max(track.bytes_per_sector for track in self._discimage.tracks)
            self._image_info.image_size = sum(track.sectors * track.bytes_per_sector for track in self._discimage.tracks)
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
            logger.debug(f"Disc type: {enum_name(MediaType, self._discimage.disktype)}")
            logger.debug(f"MCN: {self._discimage.mcn}")
            logger.debug(f"Barcode: {self._discimage.barcode}")
            logger.debug(f"Disc ID: {self._discimage.disk_id}")
            logger.debug(f"Comment: {self._discimage.comment}")
            logger.debug(f"Number of tracks: {len(self._discimage.tracks)}")
        
            for i, track in enumerate(self._discimage.tracks):
                logger.debug(f"Track {track.sequence} information:")
                logger.debug(f"  Bytes per sector: {track.bytes_per_sector}")
                logger.debug(f"  Pregap: {track.pregap} sectors")
                logger.debug(f"  Data: {track.sectors} sectors starting at sector {track.start_sector}")
                logger.debug(f"  Type: {enum_name(TrackType, track.type)}")
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
            
            self.update_reader()
            return ErrorNumber.NoError

        except Exception as ex:
            logger.error(f"Exception trying to open image file: {image_filter.filename}")
            logger.exception(ex)
            return ErrorNumber.UnexpectedException

        finally:
            if hasattr(self, '_data_stream') and self._data_stream:
                self._data_stream.close()

    def _update_readable_sector_tags(self, tags):
        """
        Update the list of readable sector tags in the image info.
        
        :param tags: List of SectorTagType to be added
        """
        for tag in tags:
            if tag not in self._image_info.readable_sector_tags:
                self._image_info.readable_sector_tags.append(tag)

    def _detect_track_type(self, track: CdrdaoTrack) -> TrackType:
        for s in range(225, min(750, track.sectors)):
            sync_test = bytearray(12)
            sect_test = bytearray(2352)

            pos = track.trackfile.offset + s * 2352

            stream = track.trackfile.datafilter.get_data_fork_stream()
            if pos >= stream.seek(0, io.SEEK_END):
                break

            stream.seek(pos)
            stream.readinto(sect_test)
            sync_test[:] = sect_test[:12]

            if sync_test != Sector.SYNC_MARK:
                continue

            if self.cdrdao._scrambled:
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

    def _get_sector_layout(self, track: 'CdrdaoTrack') -> Tuple[int, int, int, bool]:
        sector_offset = 0
        sector_size = cdrdao_track_type_to_cooked_bytes_per_sector(track.tracktype)
        sector_skip = 0
        mode2 = False

        if track.tracktype in [CDRDAO_TRACK_TYPE_MODE1, CDRDAO_TRACK_TYPE_MODE2_FORM1]:
            sector_offset = 0
            sector_skip = 0
        elif track.tracktype == CDRDAO_TRACK_TYPE_MODE2_FORM2:
            sector_offset = 0
            sector_skip = 0
        elif track.tracktype in [CDRDAO_TRACK_TYPE_MODE2, CDRDAO_TRACK_TYPE_MODE2_MIX]:
            mode2 = True
            sector_offset = 0
            sector_skip = 0
        elif track.tracktype == CDRDAO_TRACK_TYPE_AUDIO:
            sector_offset = 0
            sector_skip = 0
        elif track.tracktype == CDRDAO_TRACK_TYPE_MODE1_RAW:
            sector_offset = 16
            sector_skip = 288
        elif track.tracktype == CDRDAO_TRACK_TYPE_MODE2_RAW:
            mode2 = True
            sector_offset = 0
            sector_skip = 0
        else:
            raise ValueError(f"Unsupported track type: {track.tracktype}")

        if track.subchannel:
            sector_skip += 96

        return sector_offset, sector_size, sector_skip, mode2


    def _create_full_toc(self, create_c0_entry: bool = False) -> None:
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

            if track_control == 0 and track.tracktype != CDRDAO_TRACK_TYPE_AUDIO:
                track_control = 0x04  # Data track flag

            # Lead-Out
            if track.sequence > current_session and current_session != 0:
                leadout_amsf = lba_to_msf(track.start_sector - 150) # subtract 150 for lead-in
                leadout_pmsf = lba_to_msf(max(t.start_sector for t in self._discimage.tracks))

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

                # This seems to be constant? It should not exist on CD-ROM but CloneCD creates them anyway
                # Format seems like ATIP, but ATIP should not be as 0xC0 in TOC...
                if create_c0_entry:
                    track_descriptors.append(TrackDataDescriptor(
                        session_number=current_session,
                        point=0xC0,
                        adr=5,
                        control=0,
                        min=128,
                        pmin=97,
                        psec=25
                    ))

            # Lead-in
            if track.sequence > current_session:
                current_session = track.sequence
                ending_track_number = session_ending_track.get(current_session, 0)

                leadin_pmsf = lba_to_msf(next((t.start_sector + t.sectors for t in self._discimage.tracks if t.sequence == ending_track_number), 0))

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

            pmsf = lba_to_msf(track.indexes.get(1, track.start_sector))

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
