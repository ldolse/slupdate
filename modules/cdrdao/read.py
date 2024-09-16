import re
import os
import io
import datetime
from typing import Tuple, Optional, List, Union
from .utilities import *
from .structs import CdrdaoTrack
from .constants import *
from .structs import CdrdaoTrackFile, CdrdaoTrack, CdrdaoDisc
from modules.error_number import ErrorNumber
from modules.CD.cd_types import SectorTagType, MediaTagType, Track, Session, TrackSubchannelType
from modules.CD.sector import Sector
from modules.CD.cd_checksums import CdChecksums
from modules.ifilter import IFilter
from modules.CD.cd_types import (
    TrackType, TrackSubchannelType, SectorTagType, MediaType, 
    MediaTagType, MetadataMediaType,
    Track, Session, Partition, enum_name
)

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CdrdaoRead:
    def __init__(self, cdrdao):
        self.cdrdao = cdrdao
        self._discimage = None
        self._offset_map = None
        self._data_stream = None
        self._scrambled = False

    def update(self, discimage, offset_map, data_stream, scrambled):
        self._discimage = discimage
        self._offset_map = offset_map
        self._data_stream = data_stream
        self._scrambled = scrambled

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
    
        cdrdao_track = next((t for t in self._discimage.tracks if t.sequence == track), None)
        if cdrdao_track is None:
            return ErrorNumber.SectorNotFound, None
    
        if length > cdrdao_track.sectors:
            return ErrorNumber.OutOfRange, None
    
        sector_offset = 0
        sector_size = 0
        sector_skip = 0
        mode2 = False
    
        if cdrdao_track.tracktype in [CDRDAO_TRACK_TYPE_MODE1, CDRDAO_TRACK_TYPE_MODE2_FORM1]:
            sector_offset, sector_size, sector_skip = 0, 2048, 0
        elif cdrdao_track.tracktype == CDRDAO_TRACK_TYPE_MODE2_FORM2:
            sector_offset, sector_size, sector_skip = 0, 2324, 0
        elif cdrdao_track.tracktype in [CDRDAO_TRACK_TYPE_MODE2, CDRDAO_TRACK_TYPE_MODE2_MIX]:
            mode2 = True
            sector_offset, sector_size, sector_skip = 0, 2336, 0
        elif cdrdao_track.tracktype == CDRDAO_TRACK_TYPE_AUDIO:
            sector_offset, sector_size, sector_skip = 0, 2352, 0
        elif cdrdao_track.tracktype == CDRDAO_TRACK_TYPE_MODE1_RAW:
            sector_offset, sector_size, sector_skip = 16, 2048, 288
        elif cdrdao_track.tracktype == CDRDAO_TRACK_TYPE_MODE2_RAW:
            mode2 = True
            sector_offset, sector_size, sector_skip = 0, 2352, 0
        else:
            return ErrorNumber.NotSupported, None
    
        if cdrdao_track.subchannel:
            sector_skip += 96
    
        buffer = bytearray(sector_size * length)
        
        with cdrdao_track.trackfile.datafilter.get_data_fork_stream() as stream:
            stream.seek(cdrdao_track.trackfile.offset + (sector_address * (sector_offset + sector_size + sector_skip)))
    
            if mode2:
                mode2_buffer = bytearray((sector_size + sector_skip) * length)
                stream.readinto(mode2_buffer)
                buffer = bytearray()
                for i in range(length):
                    sector = mode2_buffer[i*(sector_size + sector_skip):i*(sector_size + sector_skip) + sector_size]
                    if self.cdrdao._scrambled:
                        sector = Sector.scramble(sector)
                    buffer.extend(Sector.get_user_data_from_mode2(sector))
            elif sector_offset == 0 and sector_skip == 0:
                stream.readinto(buffer)
                if self.cdrdao._scrambled:
                    buffer = Sector.scramble(buffer)
            else:
                for i in range(length):
                    stream.seek(sector_offset, io.SEEK_CUR)
                    sector = bytearray(sector_size)
                    stream.readinto(sector)
                    if self.cdrdao._scrambled:
                        sector = Sector.scramble(sector)
                    buffer[i*sector_size:(i+1)*sector_size] = sector
                    stream.seek(sector_skip, io.SEEK_CUR)
    
        if cdrdao_track.tracktype == CDRDAO_TRACK_TYPE_AUDIO:
            buffer = swap_audio_endianness(buffer)
    
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
    
        if cdrdao_track.tracktype == CDRDAO_TRACK_TYPE_AUDIO:
            # Swap endianness for audio tracks
            buffer = swap_audio_endianness(buffer)
    
        return ErrorNumber.NoError, bytes(buffer[:sector_size * length])
    
    def read_sector_tag(self, sector_address: int, tag: SectorTagType, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        return self.read_sectors_tag(sector_address, 1, tag, track)

    def read_sectors_tag(self, sector_address: int, length: int, tag: SectorTagType, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        if track is None:
            for track_sequence, start_sector in self._offset_map.items():
                if sector_address >= start_sector:
                    track = next((t for t in self._discimage.tracks if t.sequence == track_sequence), None)
                    if track and sector_address - start_sector < track.sectors:
                        return self.read_sectors_tag(sector_address - start_sector, length, tag, track_sequence)
            return ErrorNumber.SectorNotFound, None
    
        if tag in [SectorTagType.CdTrackFlags, SectorTagType.CdTrackIsrc]:
            track = sector_address
    
        cdrdao_track = next((t for t in self._discimage.tracks if t.sequence == track), None)
        if cdrdao_track is None:
            return ErrorNumber.SectorNotFound, None
    
        if length > cdrdao_track.sectors:
            return ErrorNumber.OutOfRange, None
    
        if cdrdao_track.tracktype == CDRDAO_TRACK_TYPE_AUDIO:
            return ErrorNumber.NotSupported, None
    
        if tag == SectorTagType.CdTrackFlags:
            return self._read_track_flags(cdrdao_track)
        elif tag == SectorTagType.CdTrackIsrc:
            return self._read_track_isrc(cdrdao_track)
        elif tag == SectorTagType.CdSectorSubchannel:
            return self._read_subchannel(cdrdao_track, sector_address, length)
    
        try:
            sector_offset, sector_size, sector_skip = get_tag_layout(cdrdao_track, tag)
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
    
    def _read_track_flags(self, track: 'CdrdaoTrack') -> Tuple[ErrorNumber, Optional[bytes]]:
        flags = 0
        if track.tracktype != CDRDAO_TRACK_TYPE_AUDIO:
            flags |= 0x04  # Data track
        if track.flag_dcp:
            flags |= 0x02  # Digital copy permitted
        if track.flag_4ch:
            flags |= 0x08  # Four channel audio
        if track.flag_pre:
            flags |= 0x01  # Pre-emphasis
        return ErrorNumber.NoError, bytes([flags])
    
    def _read_track_isrc(self, track: 'CdrdaoTrack') -> Tuple[ErrorNumber, Optional[bytes]]:
        if track.isrc:
            return ErrorNumber.NoError, track.isrc.encode('ascii')
        return ErrorNumber.NoData, None
    
    def _read_subchannel(self, track: 'CdrdaoTrack', sector_address: int, length: int) -> Tuple[ErrorNumber, Optional[bytes]]:
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
    
        :param session: Either a Session object or a session number
        :return: A list of Track objects belonging to the specified session
        """
        if isinstance(session, Session):
            return self.get_session_tracks(session.sequence)
        return [track for track in self.tracks if track.session == session]
    
    def read_media_tag(self, tag: MediaTagType) -> Tuple[ErrorNumber, Optional[bytes]]:
        """
        Reads a specific media tag from the CD image.
        This method is part of the public interface and is meant to be called by external components of the Aaru system.
        """
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
        elif tag == MediaTagType.CD_TEXT:
            if self._cdtext:
                return ErrorNumber.NoError, self._cdtext
            else:
                return ErrorNumber.NoData, None
        else:
            return ErrorNumber.NotSupported, None

    def open(self, image_filter: IFilter) -> ErrorNumber:
        
        if image_filter is None:
            return ErrorNumber.NoSuchFile

        self._cdrdao_filter = image_filter

        try:
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
            self._image_info.media_type = determine_media_type()
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
