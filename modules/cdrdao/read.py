import io
from typing import Tuple, Optional, List, Union
from .utilities import *
from .structs import CdrdaoTrack
from .constants import *
from .structs import CdrdaoTrack
from modules.error_number import ErrorNumber
from modules.CD.subchannel import Subchannel
from modules.CD.sector import Sector
from modules.CD.cd_checksums import CdChecksums
from modules.checksums import CRC16CCITTContext
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

    def _check_initialization(self):
        if not all([self._discimage, self._offset_map, self._data_stream]):
            raise ValueError("CdrdaoRead not properly initialized. Call update() first.")

    def read_sector(self, sector_address: int, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        self._check_initialization()
        return self.read_sectors(sector_address, 1, track)

    def read_sectors(self, sector_address: int, length: int, track: int) -> Tuple[ErrorNumber, Optional[bytes]]:
        aaru_track = next((ct for ct in self._discimage.tracks if ct.sequence == track), None)
        
        if not aaru_track:
            return ErrorNumber.SectorNotFound, None

        if length > aaru_track.sectors:
            return ErrorNumber.OutOfRange, None

        sector_offset, sector_size, sector_skip, mode2 = self._get_sector_layout(aaru_track)

        buffer = bytearray(sector_size * length)

        self._data_stream.seek(aaru_track.trackfile.offset + 
                            sector_address * (sector_offset + sector_size + sector_skip))

        if mode2:
            mode2_ms = BytesIO()
            temp_buffer = self._data_stream.read((sector_size + sector_skip) * length)

            for i in range(length):
                sector = temp_buffer[i*(sector_size + sector_skip):i*(sector_size + sector_skip) + sector_size]
                sector = Sector.get_user_data_from_mode2(sector)
                mode2_ms.write(sector)

            buffer = mode2_ms.getvalue()
        elif sector_offset == 0 and sector_skip == 0:
            buffer = self._data_stream.read(sector_size * length)
        else:
            for i in range(length):
                self._data_stream.seek(sector_offset, 1)  # 1 is equivalent to SeekOrigin.Current
                sector = self._data_stream.read(sector_size)
                self._data_stream.seek(sector_skip, 1)
                buffer[i*sector_size:(i+1)*sector_size] = sector

        # cdrdao audio tracks are endian swapped corresponding to Aaru
        if aaru_track.tracktype == CDRDAO_TRACK_TYPE_AUDIO:
            buffer = swap_audio_endianness(buffer)

        return ErrorNumber.NoError, bytes(buffer)
    
    def read_sector_long(self, sector_address: int, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        self._check_initialization()
        return self.read_sectors_long(sector_address, 1, track)
    
    def read_sectors_long(self, sector_address: int, length: int, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        self._check_initialization()
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

        sector_size = cdrdao_track.bps
        buffer = bytearray(sector_size * length)

        with cdrdao_track.trackfile.datafilter.get_data_fork_stream() as stream:
            stream.seek(cdrdao_track.trackfile.offset + (sector_address * sector_size))
            bytes_read = stream.readinto(buffer)

            if bytes_read != len(buffer):
                logger.warning(f"Expected to read {len(buffer)} bytes, but read {bytes_read} bytes")
                logger.debug(f"Track info: bps={cdrdao_track.bps}, subchannel={cdrdao_track.subchannel}, tracktype={cdrdao_track.tracktype}")
                
                # Adjust buffer size to match what was actually read
                buffer = buffer[:bytes_read]

        return ErrorNumber.NoError, bytes(buffer)
    
    def read_sector_tag(self, sector_address: int, tag: SectorTagType, track: Optional[int] = None) -> Tuple[ErrorNumber, Optional[bytes]]:
        self._check_initialization()
        if track is None:
            for track_sequence, start_sector in self._offset_map.items():
                if sector_address >= start_sector:
                    track = next((t for t in self._discimage.tracks if t.sequence == track_sequence), None)
                    if track and sector_address - start_sector < track.sectors:
                        return self.read_sector_tag(sector_address - start_sector, tag, track_sequence)
            return ErrorNumber.SectorNotFound, None

        cdrdao_track = next((t for t in self._discimage.tracks if t.sequence == track), None)
        if cdrdao_track is None:
            return ErrorNumber.SectorNotFound, None

        if tag == SectorTagType.CdSectorSubchannel:
            if not cdrdao_track.subchannel:
                return ErrorNumber.NotSupported, None
            
            # Read the full sector
            error, sector_data = self.read_sectors_long(sector_address, 1, track)
            if error != ErrorNumber.NoError:
                return error, None
            
            # Extract subchannel data (last 96 bytes)
            subchannel_data = sector_data[-96:]
            return ErrorNumber.NoError, subchannel_data

        # Handle other tag types...
        # (Keep the existing logic for other tag types)

        return ErrorNumber.NotSupported, None
    
    def _read_track_flags(self, track: 'CdrdaoTrack') -> Tuple[ErrorNumber, Optional[bytes]]:
        flags = calculate_track_flags(track)
        return ErrorNumber.NoError, bytes([flags])
    
    def _read_track_isrc(self, track: 'CdrdaoTrack') -> Tuple[ErrorNumber, Optional[bytes]]:
        if track.isrc:
            return ErrorNumber.NoError, track.isrc.encode('ascii')
        return ErrorNumber.NoData, None
    
    def _read_subchannel(self, track: 'CdrdaoTrack', sector_address: int, length: int) -> Tuple[ErrorNumber, Optional[bytes]]:
        if not track.subchannel:
            logger.warning(f"Track {track.sequence} does not have subchannel data")
            return ErrorNumber.NotSupported, None
        
        buffer = bytearray(96 * length)
        try:
            with track.trackfile.datafilter.get_data_fork_stream() as stream:
                # Calculate the correct offset for the subchannel data
                sector_size = 2352 + 96  # Main sector + subchannel
                offset = track.trackfile.offset + (sector_address * sector_size) + 2352
                stream.seek(offset)
                logger.debug(f"Seeking to offset {offset} for subchannel data (track {track.sequence}, sector {sector_address})")
                bytes_read = stream.readinto(buffer)
                
                if bytes_read != 96 * length:
                    logger.warning(f"Expected to read {96 * length} bytes, but read {bytes_read} bytes")
                    return ErrorNumber.InOutError, None
                
                # Deinterleave the subchannel data
                deinterleaved = Subchannel.deinterleave(buffer)
                return ErrorNumber.NoError, bytes(deinterleaved)
        except Exception as e:
            logger.error(f"Error reading subchannel data: {str(e)}")
            return ErrorNumber.InOutError, None
    
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

    def validate_subchannel(self, sector_address: int, track: int) -> bool:
        logger.debug(f"Validating subchannel for track {track}, sector {sector_address}")
        error, subchannel_data = self.read_sector_tag(sector_address, SectorTagType.CdSectorSubchannel, track)
        
        if error != ErrorNumber.NoError or subchannel_data is None:
            logger.warning(f"Failed to read subchannel data: {error}")
            return False
        
        logger.debug(f"Read {len(subchannel_data)} bytes of subchannel data")
        
        if len(subchannel_data) != 96:
            logger.warning(f"Unexpected subchannel data size: {len(subchannel_data)} bytes")
            return False

        # Deinterleave the subchannel data
        deinterleaved = Subchannel.deinterleave(subchannel_data)
        
        # Check P subchannel (should be all 0xFF for lead-in)
        p_subchannel = deinterleaved[:12]
        logger.debug(f"P subchannel data: {p_subchannel.hex()}")
        if not all(b == 0xFF for b in p_subchannel):
            logger.warning(f"Invalid P subchannel data: {p_subchannel.hex()}")
            return False
        
        # Check Q subchannel structure
        q_subchannel = deinterleaved[12:24]
        logger.debug(f"Q subchannel data: {q_subchannel.hex()}")
        try:
            q_info = Subchannel.prettify_q(q_subchannel, True, sector_address, False, True, False)
            logger.debug(f"Q subchannel info: {q_info}")
        except Exception as e:
            logger.error(f"Error processing Q subchannel: {str(e)}")
            return False
        
        # Calculate CRC
        calculated_crc = CRC16CCITTContext.calculate(q_subchannel[:10])
        stored_crc = (q_subchannel[10] << 8) | q_subchannel[11]
        
        if calculated_crc != stored_crc:
            logger.warning(f"CRC mismatch: calculated {calculated_crc:04X}, stored {stored_crc:04X}")
            return False
        
        return True
    