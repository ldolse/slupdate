from dataclasses import dataclass, field
from typing import List, Dict
import struct
from typing import Optional
from modules.CD.cd_types import TocControl, TocAdr, MediaTagType, SectorTagType, Track, TrackType, CdFlags
import logging

logger = logging.getLogger(__name__)

@dataclass
class TrackDataDescriptor:
    session_number: int = 0
    """Byte 0 Session number in hex"""
    
    adr: int = 0
    """Byte 1, bits 7 to 4 Type of information in Q subchannel of block where this TOC entry was found"""
    
    control: int = 0
    """Byte 1, bits 3 to 0 Track attributes"""
    
    tno: int = 0
    """Byte 2"""
    
    point: int = 0
    """Byte 3"""
    
    min: int = 0
    """Byte 4"""
    
    sec: int = 0
    """Byte 5"""
    
    frame: int = 0
    """Byte 6"""
    
    zero: int = 0
    """Byte 7, CD only"""
    
    hour: int = 0
    """Byte 7, bits 7 to 4, DDCD only"""
    
    phour: int = 0
    """Byte 7, bits 3 to 0, DDCD only"""
    
    pmin: int = 0
    """Byte 8"""
    
    psec: int = 0
    """Byte 9"""
    
    pframe: int = 0
    """Byte 10"""

@dataclass
class CDFullTOC:
    data_length: int = 0
    """Total size of returned session information minus this field"""
    
    first_complete_session: int = 0
    """First complete session number in hex"""
    
    last_complete_session: int = 0
    """Last complete session number in hex"""
    
    track_descriptors: List[TrackDataDescriptor] = field(default_factory=list)
    """Track descriptors"""    

class FullTOC:
    MODULE_NAME = "CD full TOC decoder"

    @staticmethod
    def decode(cd_full_toc_response: bytes) -> CDFullTOC:
        logger.debug(f"Received TOC data content: {cd_full_toc_response.hex()}")
        if not cd_full_toc_response or len(cd_full_toc_response) <= 4:
            logger.debug(f"TOC data too short: {len(cd_full_toc_response)} bytes")
            return None

        decoded = CDFullTOC()
        decoded.data_length = struct.unpack('>H', cd_full_toc_response[0:2])[0]
        decoded.first_complete_session = cd_full_toc_response[2]
        decoded.last_complete_session = cd_full_toc_response[3]

        logger.debug(f"TOC data length: {len(cd_full_toc_response)} bytes")
        logger.debug(f"Decoded data length: {decoded.data_length}")
        logger.debug(f"First complete session: {decoded.first_complete_session}")
        logger.debug(f"Last complete session: {decoded.last_complete_session}")

        if decoded.data_length + 2 != len(cd_full_toc_response):
            logger.debug(f"Expected CDFullTOC size {decoded.data_length + 2} bytes is not received size {len(cd_full_toc_response)} bytes, not decoding")
            return None

        for i in range((decoded.data_length - 2) // 11):
            descriptor = TrackDataDescriptor()
            offset = i * 11 + 4
            descriptor.session_number = cd_full_toc_response[offset]
            descriptor.adr = (cd_full_toc_response[offset + 1] & 0xF0) >> 4
            descriptor.control = cd_full_toc_response[offset + 1] & 0x0F
            descriptor.tno = cd_full_toc_response[offset + 2]
            descriptor.point = cd_full_toc_response[offset + 3]
            descriptor.min = cd_full_toc_response[offset + 4]
            descriptor.sec = cd_full_toc_response[offset + 5]
            descriptor.frame = cd_full_toc_response[offset + 6]
            descriptor.zero = cd_full_toc_response[offset + 7]
            descriptor.hour = (cd_full_toc_response[offset + 7] & 0xF0) >> 4
            descriptor.phour = cd_full_toc_response[offset + 7] & 0x0F
            descriptor.pmin = cd_full_toc_response[offset + 8]
            descriptor.psec = cd_full_toc_response[offset + 9]
            descriptor.pframe = cd_full_toc_response[offset + 10]
            decoded.track_descriptors.append(descriptor)

        logger.debug(f"Decoded {len(decoded.track_descriptors)} track descriptors")
        return decoded

    @staticmethod
    def prettify(cd_full_toc_response: Optional[CDFullTOC]) -> Optional[str]:
        if cd_full_toc_response is None:
            return None
    
        response = cd_full_toc_response
        output = []
    
        last_session = 0
    
        output.append(f"First complete session number: {response.first_complete_session}")
        output.append(f"Last complete session number: {response.last_complete_session}")
    
        for descriptor in response.track_descriptors:
            if ((descriptor.control & 0x08) == 0x08 or
                descriptor.adr not in [1, 4, 5, 6] or
                descriptor.tno != 0):
                output.append("Unknown TOC entry format, printing values as is:")
                output.append(f"SessionNumber = {descriptor.session_number}")
                output.append(f"ADR = {descriptor.adr}")
                output.append(f"CONTROL = {descriptor.control}")
                output.append(f"TNO = {descriptor.tno}")
                output.append(f"POINT = {descriptor.point}")
                output.append(f"Min = {descriptor.min}")
                output.append(f"Sec = {descriptor.sec}")
                output.append(f"Frame = {descriptor.frame}")
                output.append(f"HOUR = {descriptor.hour}")
                output.append(f"PHOUR = {descriptor.phour}")
                output.append(f"PMIN = {descriptor.pmin}")
                output.append(f"PSEC = {descriptor.psec}")
                output.append(f"PFRAME = {descriptor.pframe}")
            else:
                if descriptor.session_number > last_session:
                    output.append(f"Session {descriptor.session_number}")
                    last_session = descriptor.session_number
    
                if descriptor.adr in [1, 4]:
                    if descriptor.point == 0xA0:
                        if descriptor.adr == 4:
                            output.append(f"First video track number: {descriptor.pmin}")
                            if descriptor.psec == 0x10:
                                output.append("CD-V single in NTSC format with digital stereo sound")
                            elif descriptor.psec == 0x11:
                                output.append("CD-V single in NTSC format with digital bilingual sound")
                            elif descriptor.psec == 0x12:
                                output.append("CD-V disc in NTSC format with digital stereo sound")
                            elif descriptor.psec == 0x13:
                                output.append("CD-V disc in NTSC format with digital bilingual sound")
                            elif descriptor.psec == 0x20:
                                output.append("CD-V single in PAL format with digital stereo sound")
                            elif descriptor.psec == 0x21:
                                output.append("CD-V single in PAL format with digital bilingual sound")
                            elif descriptor.psec == 0x22:
                                output.append("CD-V disc in PAL format with digital stereo sound")
                            elif descriptor.psec == 0x23:
                                output.append("CD-V disc in PAL format with digital bilingual sound")
                        elif descriptor.adr == 1:
                            output.append(f"First track number: {descriptor.pmin} (")
                            if (descriptor.control & 0x0D) == TocControl.TwoChanNoPreEmph.value:
                                output.append("Stereo audio track with no pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.TwoChanPreEmph.value:
                                output.append("Stereo audio track with 50/15 us pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.FourChanNoPreEmph.value:
                                output.append("Quadraphonic audio track with no pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.FourChanPreEmph.value:
                                output.append("Quadraphonic audio track with 50/15 us pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.DataTrack.value:
                                output.append("Data track recorded uninterrupted")
                            elif (descriptor.control & 0x0D) == TocControl.DataTrackIncremental.value:
                                output.append("Data track recorded incrementally")
                            output.append(")")
                            output.append(f"Disc type: {descriptor.psec}")
                    elif descriptor.point == 0xA1:
                        if descriptor.adr == 4:
                            output.append(f"Last video track number: {descriptor.pmin}")
                        elif descriptor.adr == 1:
                            output.append(f"Last track number: {descriptor.pmin} (")
                            if (descriptor.control & 0x0D) == TocControl.TwoChanNoPreEmph.value:
                                output.append("Stereo audio track with no pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.TwoChanPreEmph.value:
                                output.append("Stereo audio track with 50/15 us pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.FourChanNoPreEmph.value:
                                output.append("Quadraphonic audio track with no pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.FourChanPreEmph.value:
                                output.append("Quadraphonic audio track with 50/15 us pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.DataTrack.value:
                                output.append("Data track recorded uninterrupted")
                            elif (descriptor.control & 0x0D) == TocControl.DataTrackIncremental.value:
                                output.append("Data track recorded incrementally")
                            output.append(")")
                    elif descriptor.point == 0xA2:
                        if descriptor.phour > 0:
                            output.append(f"Lead-out start position: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe} ({descriptor.phour})")
                        else:
                            output.append(f"Lead-out start position: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe}")
                        if (descriptor.control & 0x0D) in [TocControl.TwoChanNoPreEmph, TocControl.TwoChanPreEmph, TocControl.FourChanNoPreEmph, TocControl.FourChanPreEmph]:
                            output.append("Lead-out is audio type")
                        elif (descriptor.control & 0x0D) in [TocControl.DataTrack, TocControl.DataTrackIncremental]:
                            output.append("Lead-out is data type")
                    elif descriptor.point == 0xF0:
                        output.append(f"Book type: {descriptor.pmin}")
                        output.append(f"Material type: {descriptor.psec}")
                        output.append(f"Moment of inertia: {descriptor.pframe}")
                        if descriptor.phour > 0:
                            output.append(f"Absolute time: {descriptor.min}:{descriptor.sec}:{descriptor.frame} ({descriptor.hour})")
                        else:
                            output.append(f"Absolute time: {descriptor.min}:{descriptor.sec}:{descriptor.frame}")
                    elif 0x01 <= descriptor.point <= 0x63:
                        if descriptor.adr == 4:
                            output.append(f"Video track {descriptor.point} starts at {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe}")
                        else:
                            data = (descriptor.control & 0x0D) in [TocControl.DataTrack, TocControl.DataTrackIncremental]
                            if descriptor.phour > 0:
                                output.append(f"{'Data' if data else 'Audio'} track {descriptor.point} starts at {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe} ({descriptor.phour}) (")
                            else:
                                output.append(f"{'Data' if data else 'Audio'} track {descriptor.point} starts at {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe} (")
                            if (descriptor.control & 0x0D) == TocControl.TwoChanNoPreEmph.value:
                                output.append("Stereo audio track with no pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.TwoChanPreEmph.value:
                                output.append("Stereo audio track with 50/15 us pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.FourChanNoPreEmph.value:
                                output.append("Quadraphonic audio track with no pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.FourChanPreEmph.value:
                                output.append("Quadraphonic audio track with 50/15 us pre-emphasis")
                            elif (descriptor.control & 0x0D) == TocControl.DataTrack.value:
                                output.append("Data track recorded uninterrupted")
                            elif (descriptor.control & 0x0D) == TocControl.DataTrackIncremental.value:
                                output.append("Data track recorded incrementally")
                            output.append(")")
                    else:
                        output.append(f"ADR = {descriptor.adr}")
                        output.append(f"CONTROL = {descriptor.control}")
                        output.append(f"TNO = {descriptor.tno}")
                        output.append(f"POINT = {descriptor.point}")
                        output.append(f"Min = {descriptor.min}")
                        output.append(f"Sec = {descriptor.sec}")
                        output.append(f"Frame = {descriptor.frame}")
                        output.append(f"HOUR = {descriptor.hour}")
                        output.append(f"PHOUR = {descriptor.phour}")
                        output.append(f"PMIN = {descriptor.pmin}")
                        output.append(f"PSEC = {descriptor.psec}")
                        output.append(f"PFRAME = {descriptor.pframe}")
                elif descriptor.adr == 5:
                    if descriptor.point == 0xB0:
                        if descriptor.phour > 0:
                            output.append(f"Start of next possible program in the recordable area of the disc: {descriptor.min}:{descriptor.sec}:{descriptor.frame} ({descriptor.hour})")
                            output.append(f"Maximum start of outermost Lead-out in the recordable area of the disc: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe} ({descriptor.phour})")
                        else:
                            output.append(f"Start of next possible program in the recordable area of the disc: {descriptor.min}:{descriptor.sec}:{descriptor.frame}")
                            output.append(f"Maximum start of outermost Lead-out in the recordable area of the disc: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe}")
                    elif descriptor.point == 0xB1:
                        output.append(f"Number of skip interval pointers: {descriptor.pmin}")
                        output.append(f"Number of skip track pointers: {descriptor.psec}")
                    elif descriptor.point in [0xB2, 0xB3, 0xB4]:
                        output.append(f"Skip track: {descriptor.min}")
                        output.append(f"Skip track: {descriptor.sec}")
                        output.append(f"Skip track: {descriptor.frame}")
                        output.append(f"Skip track: {descriptor.zero}")
                        output.append(f"Skip track: {descriptor.pmin}")
                        output.append(f"Skip track: {descriptor.psec}")
                        output.append(f"Skip track: {descriptor.pframe}")
                    elif descriptor.point == 0xC0:
                        output.append(f"Optimum recording power: {descriptor.min}")
                        if descriptor.phour > 0:
                            output.append(f"Start time of the first Lead-in area in the disc: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe} ({descriptor.phour})")
                        else:
                            output.append(f"Start time of the first Lead-in area in the disc: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe}")
                    elif descriptor.point == 0xC1:
                        output.append("Copy of information of A1 from ATIP found:")
                        output.append(f"Min = {descriptor.min}")
                        output.append(f"Sec = {descriptor.sec}")
                        output.append(f"Frame = {descriptor.frame}")
                        output.append(f"Zero = {descriptor.zero}")
                        output.append(f"PMIN = {descriptor.pmin}")
                        output.append(f"PSEC = {descriptor.psec}")
                        output.append(f"PFRAME = {descriptor.pframe}")
                    elif descriptor.point == 0xCF:
                        if descriptor.phour > 0:
                            output.append(f"Start position of outer part lead-in area: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe} ({descriptor.phour})")
                            output.append(f"Stop position of inner part lead-out area: {descriptor.min}:{descriptor.sec}:{descriptor.frame} ({descriptor.hour})")
                        else:
                            output.append(f"Start position of outer part lead-in area: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe}")
                            output.append(f"Stop position of inner part lead-out area: {descriptor.min}:{descriptor.sec}:{descriptor.frame}")
                    elif 0x01 <= descriptor.point <= 0x40:
                        output.append(f"Start time for interval that should be skipped: {descriptor.pmin}:{descriptor.psec}:{descriptor.pframe}")
                        output.append(f"Ending time for interval that should be skipped: {descriptor.min}:{descriptor.sec}:{descriptor.frame}")
                    else:
                        output.append(f"ADR = {descriptor.adr}")
                        output.append(f"CONTROL = {descriptor.control}")
                        output.append(f"TNO = {descriptor.tno}")
                        output.append(f"POINT = {descriptor.point}")
                        output.append(f"Min = {descriptor.min}")
                        output.append(f"Sec = {descriptor.sec}")
                        output.append(f"Frame = {descriptor.frame}")
                        output.append(f"HOUR = {descriptor.hour}")
                        output.append(f"PHOUR = {descriptor.phour}")
                        output.append(f"PMIN = {descriptor.pmin}")
                        output.append(f"PSEC = {descriptor.psec}")
                        output.append(f"PFRAME = {descriptor.pframe}")
                elif descriptor.adr == 6:
                    id_ = (descriptor.min << 16) + (descriptor.sec << 8) + descriptor.frame
                    output.append(f"Disc ID: {id_ & 0x00FFFFFF:06X}")
    
        return "\n".join(output)

    @staticmethod
    def prettify_bytes(cd_full_toc_response: bytes) -> str:
        decoded = FullTOC.decode(cd_full_toc_response)
        return FullTOC.prettify(decoded)

    @staticmethod
    def create(tracks: List[Track], track_flags: Dict[int, int], create_c0_entry: bool = False) -> 'CDFullTOC':
        toc = FullTOC.CDFullTOC()
        session_ending_track = {}
        toc.first_complete_session = 255  # byte.MaxValue
        toc.last_complete_session = 0  # byte.MinValue
        track_descriptors = []
        current_track = 0

    
        for track in sorted(tracks, key=lambda t: (t.session, t.sequence)):
            if track.session < toc.first_complete_session:
                toc.first_complete_session = track.session
    
            if track.session <= toc.last_complete_session:
                current_track = track.sequence
                continue
    
            if toc.last_complete_session > 0:
                session_ending_track[toc.last_complete_session] = current_track
    
            toc.last_complete_session = track.session
    
        session_ending_track.setdefault(toc.last_complete_session, 
                                        max(t.sequence for t in tracks if t.session == toc.last_complete_session))
    
        current_session = 0
    
        for track in sorted(tracks, key=lambda t: (t.session, t.sequence)):
            track_control = track_flags.get(track.sequence, 0)
    
            if track_control == 0 and track.type != TrackType.Audio:
                track_control = CdFlags.DataTrack
    
            # Lead-Out
            if track.session > current_session and current_session != 0:
                leadout_amsf = FullTOC.lba_to_msf(track.start_sector - 150)
                leadout_pmsf = FullTOC.lba_to_msf(max(t.start_sector for t in tracks))
    
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
            if track.session > current_session:
                current_session = track.session
                ending_track_number = session_ending_track.get(current_session, 0)
    
                leadin_pmsf = FullTOC.lba_to_msf(next((t.end_sector for t in tracks if t.sequence == ending_track_number), 0) + 1)
    
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
    
            pmsf = FullTOC.lba_to_msf(track.indexes[1])
    
            # Track
            track_descriptors.append(TrackDataDescriptor(
                session_number=track.session,
                point=track.sequence,
                adr=1,
                control=track_control,
                phour=0,
                pmin=pmsf[0],
                psec=pmsf[1],
                pframe=pmsf[2]
            ))
    
        toc.track_descriptors = track_descriptors
        return toc


    @staticmethod
    def create(tracks: List['Track'], track_flags: Dict[int, int], create_c0_entry: bool = False) -> 'CDFullTOC':
        toc = CDFullTOC()
        session_ending_track: Dict[int, int] = {}
        toc.first_complete_session = 255  # byte.MaxValue
        toc.last_complete_session = 0  # byte.MinValue
        track_descriptors: List[TrackDataDescriptor] = []
        current_track = 0
    
        for track in sorted(tracks, key=lambda t: (t.session, t.sequence)):
            if track.session < toc.first_complete_session:
                toc.first_complete_session = track.session
    
            if track.session <= toc.last_complete_session:
                current_track = track.sequence
                continue
    
            if toc.last_complete_session > 0:
                session_ending_track[toc.last_complete_session] = current_track
    
            toc.last_complete_session = track.session
    
        if toc.last_complete_session not in session_ending_track:
            session_ending_track[toc.last_complete_session] = max(t.sequence for t in tracks if t.session == toc.last_complete_session)
    
        current_session = 0
    
        for track in sorted(tracks, key=lambda t: (t.session, t.sequence)):
            track_control = track_flags.get(track.sequence, 0)
    
            if track_control == 0 and track.type != TrackType.Audio:
                track_control = CdFlags.DataTrack
    
            # Lead-Out
            if track.session > current_session and current_session != 0:
                leadout_amsf = FullTOC.lba_to_msf(track.start_sector - 150)
                leadout_pmsf = FullTOC.lba_to_msf(max(t.start_sector for t in tracks))
    
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
            if track.session > current_session:
                current_session = track.session
                ending_track_number = session_ending_track.get(current_session, 0)
    
                leadin_pmsf = FullTOC.lba_to_msf(next((t.end_sector for t in tracks if t.sequence == ending_track_number), 0) + 1)
    
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
    
            pmsf = FullTOC.lba_to_msf(track.indexes[1])
    
            # Track
            track_descriptors.append(TrackDataDescriptor(
                session_number=track.session,
                point=track.sequence,
                adr=1,
                control=track_control,
                phour=0,
                pmin=pmsf[0],
                psec=pmsf[1],
                pframe=pmsf[2]
            ))
    
        toc.track_descriptors = track_descriptors
        return toc

    @staticmethod
    def lba_to_msf(sector):
        return ((sector + 150) // 75 // 60, ((sector + 150) // 75) % 60, (sector + 150) % 75)