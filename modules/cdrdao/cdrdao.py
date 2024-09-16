import io
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
from modules.error_number import ErrorNumber

from .toc import *
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
            self._full_toc = create_full_toc(self._discimage.tracks, self._track_flags, create_c0_entry=False)
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
