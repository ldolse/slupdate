import io
import os
from datetime import datetime
from typing import List, Dict, Optional, BinaryIO
from modules.ifilter import IFilter
from modules.cdrdao_filter import CDRDAOFilter

from modules.CD.atip import ATIP
from modules.CD.sector import Sector
from modules.CD.subchannel import Subchannel
from modules.CD.sector_builder import SectorBuilder
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
        self._data_stream = None
        self._catalog: Optional[str] = None
        self._cdtext: Optional[bytes] = None
        self._data_filter: Optional[IFilter] = None
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

        try:
            # parse the toc file
            error, self._discimage = parse_toc_file(image_filter)
            if error != ErrorNumber.NoError:
                return error
            
            # Process tracks and build offset map
            self.partitions = []
            self._offset_map = {}
            current_offset = 0
            partitionSequence = 0
            total_sectors = 0

            for track in self._discimage.tracks:
                partition = Partition(
                    description=f"Track {track.sequence}",
                    size=track.sectors * track.bps,
                    length=track.sectors,
                    sequence=partitionSequence,
                    offset=current_offset,
                    start=track.start_sector,
                    type=track.tracktype
                )
                self.partitions.append(partition)
                self._offset_map[track.sequence] = track.start_sector
                current_offset += partition.size
                partitionSequence += 1
                total_sectors += track.sectors
                track.type = self._detect_track_type(track)

            # Set up track flags
            self._track_flags[track.sequence] = calculate_track_flags(track)

            # Create TOC
            self._full_toc = create_full_toc(self._discimage.tracks, self._track_flags, create_c0_entry=False)
            self._image_info.readable_media_tags.append(MediaTagType.CD_FullTOC)

            # Handle CD-Text
            if hasattr(self._discimage, 'cdtext') and self._discimage.cdtext:
                self._cdtext = self._discimage.cdtext
                self._image_info.readable_media_tags.append(MediaTagType.CD_TEXT)

            # Set up readable sector tags
            self._setup_readable_sector_tags()

            # Create sessions
            self.sessions = []
            current_session = Session(
                sequence=1,
                start_track=float('inf'),
                end_track=float('-inf'),
                start_sector=0,
                end_sector=0
            )

            for track in self._discimage.tracks:
                if track.start_sector + track.sectors > self._image_info.sectors:
                    self._image_info.sectors = track.start_sector + track.sectors

                if track.sequence < current_session.start_track:
                    current_session.start_track = track.sequence
                    current_session.start_sector = track.start_sector
                if track.sequence > current_session.end_track:
                    current_session.end_track = track.sequence
                    current_session.end_sector = track.start_sector + track.sectors - 1

            self.sessions.append(current_session)
            logger.debug(f" Session info: Start sector: {self.sessions[0].start_sector}, End sector: {self.sessions[0].end_sector}")

            # Create tracks
            self.tracks = [cdrdao_track_to_track(ct) for ct in self._discimage.tracks]

            # Set image info
            self._set_image_info(image_filter)

            # Initialize sector builder
            self._sector_builder = SectorBuilder()

            # Open the data stream
            self._data_stream = image_filter.get_data_fork_stream()

            # Update reader
            self.reader.update(self._discimage, self._offset_map, self._data_stream, self._scrambled)

            # Validate subchannel data for the first track
            if self._discimage.tracks:
                first_track = self._discimage.tracks[0]
                logger.debug(f" First track info: start_sector={first_track.start_sector}, sequence={first_track.sequence}, subchannel={first_track.subchannel}, file_offset={first_track.trackfile.offset}, sectors={first_track.sectors}")
                if first_track.subchannel:
                    is_valid = self.reader.validate_subchannel(first_track.start_sector, first_track.sequence)
                    if not is_valid:
                        logger.warning("Subchannel validation failed for the first track")
                else:
                    logger.warning("First track does not have subchannel data")

            # Determine media type
            data_tracks = sum(1 for track in self._discimage.tracks if track.tracktype != CDRDAO_TRACK_TYPE_AUDIO)
            audio_tracks = len(self._discimage.tracks) - data_tracks
            mode2_tracks = sum(1 for track in self._discimage.tracks if track.tracktype in [
                CDRDAO_TRACK_TYPE_MODE2, CDRDAO_TRACK_TYPE_MODE2_FORM1, 
                CDRDAO_TRACK_TYPE_MODE2_FORM2, CDRDAO_TRACK_TYPE_MODE2_MIX, 
                CDRDAO_TRACK_TYPE_MODE2_RAW
            ])
            # Log debug information
            logger.debug(" Disc image parsing results")
            # Handle CD-Text
            if hasattr(self._discimage, 'cdtext') and self._discimage.cdtext:
                self._cdtext = self._discimage.cdtext
                self._image_info.readable_media_tags.append(MediaTagType.CD_TEXT)
                self._parse_cd_text(self._cdtext)

            logger.debug(" Disc CD-TEXT:")
            logger.debug(f" \tArranger {'is not set.' if not self._discimage.arranger else ': '+self._discimage.arranger}")
            logger.debug(f" \tComposer {'is not set.' if not self._discimage.composer else ': '+self._discimage.composer}")
            logger.debug(f" \tPerformer {'is not set.' if not self._discimage.performer else ': '+self._discimage.performer}")
            logger.debug(f" \tSongwriter {'is not set.' if not self._discimage.songwriter else ': '+self._discimage.songwriter}")
            logger.debug(f" \tTitle {'is not set.' if not self._discimage.title else ': '+self._discimage.title}")            

            logger.debug(" Disc information:")
            logger.debug(f" \tGuessed disk type: {enum_name(MediaType, self._discimage.disktype)}")
            logger.debug(f" \tBarcode {'not set.' if not self._discimage.barcode else ': '+self._discimage.barcode}")
            logger.debug(f" \tDisc ID {'not set.' if not self._discimage.disk_id else ': '+self._discimage.disk_id}")
            logger.debug(f" \tMCN {'not set.' if not self._discimage.mcn else ': '+self._discimage.mcn}")
            logger.debug(f" \tComment {'not set.' if not self._discimage.comment else ': '+self._discimage.comment}")

            logger.debug(" Track information:")
            logger.debug(f" \tDisc contains {len(self._discimage.tracks)} tracks")

            for i, track in enumerate(self._discimage.tracks, 1):
                logger.debug(f" \tTrack {track.sequence} information:")
                logger.debug(f" \t\t{track.bps} bytes per sector")
                logger.debug(f" \t\tPregap: {track.pregap} sectors")
                logger.debug(f" \t\tData: {track.sectors} sectors starting at sector {track.start_sector}")
                logger.debug(f" \t\tPostgap: {track.postgap} sectors")
                logger.debug(f" \t\tType: {enum_name(TrackType, track.type)}")
                logger.debug(f" \t\tTrack resides in file {track.trackfile.datafile}, type defined as {track.trackfile.filetype}, starting at byte {track.trackfile.offset}")
                logger.debug(f" \t\tFile offset: {track.trackfile.offset}")
                logger.debug(f" \t\tSubchannel: {'Yes' if track.subchannel else 'No'}")
                logger.debug(" \t\tIndexes:")
                for index, start in track.indexes.items():
                    logger.debug(f" \t\t\tIndex {index} starts at sector {start}")
                logger.debug(f" \t\tISRC {'is not set.' if not track.isrc else ': '+track.isrc}")
                logger.debug(f" \t\tArranger {'is not set.' if not track.arranger else ': '+track.arranger}")
                logger.debug(f" \t\tComposer {'is not set.' if not track.composer else ': '+track.composer}")
                logger.debug(f" \t\tPerformer {'is not set.' if not track.performer else ': '+track.performer}")
                logger.debug(f" \t\tSongwriter {'is not set.' if not track.songwriter else ': '+track.songwriter}")
                logger.debug(f" \t\tTitle {'is not set.' if not track.title else ': '+track.title}")

            logger.debug(" printing partition map")
            for partition in self.partitions:
                logger.debug(f" Partition sequence: {partition.sequence}")
                logger.debug(f" \tPartition name: {partition.name}")
                logger.debug(f" \tPartition description: {partition.description}")
                logger.debug(f" \tPartition type: {partition.type}")
                logger.debug(f" \tPartition starting sector: {partition.start}")
                logger.debug(f" \tPartition sectors: {partition.length}")
                logger.debug(f" \tPartition starting offset: {partition.offset}")
                logger.debug(f" \tPartition size in bytes: {partition.size}")
            
            return ErrorNumber.NoError

        except Exception as ex:
            logger.error(f"Exception trying to open image file: {image_filter.filename}")
            logger.exception(ex)
            return ErrorNumber.UnexpectedException

    def close(self):
        if self._data_stream:
            self._data_stream.close()
        if self._sub_stream:
            self._sub_stream.close()
        if self._toc_stream:
            self._toc_stream.close()

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

    def _setup_readable_sector_tags(self):
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

    def _set_image_info(self, image_filter):
        # Set image info
        self._image_info.media_type = determine_media_type(self._discimage.tracks, self.sessions)
        self._image_info.sectors = sum(track.sectors for track in self._discimage.tracks)
        if self._discimage.disktype not in [MediaType.CDG, MediaType.CDEG, MediaType.CDMIDI,
                                            MediaType.CDROMXA, MediaType.CDDA, MediaType.CDI,
                                            MediaType.CDPLUS]:
            self._image_info.sector_size = 2048  # Only data tracks
        else:
            self._image_info.sector_size = 2352  # All others
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

            if pack_type == 0x80:  # Album/Track Title
                text_buffer.extend(text)
                if pack[3] & 0x80:  # Last pack in sequence
                    self._process_cd_text(pack_type, track_number, text_buffer.decode('ascii', errors='ignore'))
                    text_buffer.clear()
            else:
                self._process_cd_text(pack_type, track_number, text.decode('ascii', errors='ignore'))

    def _process_cd_text(self, pack_type: int, track_number: int, text: str) -> None:
        if track_number == 0:  # Disc-related information
            self._process_disc_cd_text(pack_type, text)
        else:  # Track-related information
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



