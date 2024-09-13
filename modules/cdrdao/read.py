from typing import Tuple, Optional, List, Union
from .structs import CdrdaoTrack
from .helpers import *
from .constants import CDRDAO_TRACK_TYPE_AUDIO, CDRDAO_TRACK_TYPE_MODE1, CDRDAO_TRACK_TYPE_MODE2_FORM1, CDRDAO_TRACK_TYPE_MODE2_FORM2, CDRDAO_TRACK_TYPE_MODE2, CDRDAO_TRACK_TYPE_MODE2_MIX, CDRDAO_TRACK_TYPE_MODE2_RAW
from modules.error_number import ErrorNumber
from modules.CD.cd_types import SectorTagType, MediaTagType, Track, Session
from modules.CD.sector import Sector
from modules.CD.cd_checksums import CdChecksums

class CdrdaoRead:
    def read_sector(self, sector_address: int) -> Tuple[ErrorNumber, Optional[bytes]]:
        return self.read_sectors(sector_address, 1)
    
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
    
        if length > cdrdao_track.sectors:
            return ErrorNumber.OutOfRange, None
    
        sector_offset = 0
        sector_size = 0
        sector_skip = 0
        mode2 = False
    
        if cdrdao_track.tracktype in [self.CDRDAO_TRACK_TYPE_MODE1, self.CDRDAO_TRACK_TYPE_MODE2_FORM1]:
            sector_offset = 0
            sector_size = 2048
            sector_skip = 0
        elif cdrdao_track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_FORM2:
            sector_offset = 0
            sector_size = 2324
            sector_skip = 0
        elif cdrdao_track.tracktype in [self.CDRDAO_TRACK_TYPE_MODE2, self.CDRDAO_TRACK_TYPE_MODE2_MIX]:
            mode2 = True
            sector_offset = 0
            sector_size = 2336
            sector_skip = 0
        elif cdrdao_track.tracktype == self.CDRDAO_TRACK_TYPE_AUDIO:
            sector_offset = 0
            sector_size = 2352
            sector_skip = 0
        elif cdrdao_track.tracktype == self.CDRDAO_TRACK_TYPE_MODE1_RAW:
            sector_offset = 16
            sector_size = 2048
            sector_skip = 288
        elif cdrdao_track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_RAW:
            mode2 = True
            sector_offset = 0
            sector_size = 2352
            sector_skip = 0
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
                    if self._scrambled:
                        sector = Sector.scramble(sector)
                    buffer.extend(Sector.get_user_data_from_mode2(sector))
            elif sector_offset == 0 and sector_skip == 0:
                stream.readinto(buffer)
                if self._scrambled:
                    buffer = Sector.scramble(buffer)
            else:
                for i in range(length):
                    stream.seek(sector_offset, io.SEEK_CUR)
                    sector = bytearray(sector_size)
                    stream.readinto(sector)
                    if self._scrambled:
                        sector = Sector.scramble(sector)
                    buffer[i*sector_size:(i+1)*sector_size] = sector
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
        error, buffer = self.read_sectors_tag(sector_address, 1, tag, track)
        return error, buffer
    
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
    
        if cdrdao_track.tracktype == self.CDRDAO_TRACK_TYPE_AUDIO:
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
