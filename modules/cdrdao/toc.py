import io
import struct
from typing import List, Dict
from .structs import CdrdaoDisc, CdrdaoTrack
from .constants import *
from .utilities import *
from modules.CD.fulltoc import FullTOC, TrackDataDescriptor, CDFullTOC
from modules.ifilter import IFilter


def create_full_toc(tracks: List[CdrdaoTrack], track_flags: Dict[int, int], create_c0_entry: bool = False) -> bytes:
    toc = CDFullTOC()
    session_ending_track = {}
    toc.first_complete_session = 255
    toc.last_complete_session = 0
    track_descriptors = []
    current_track = 0

    for track in sorted(tracks, key=lambda t: t.sequence):
        if track.sequence < toc.first_complete_session:
            toc.first_complete_session = track.sequence

        if track.sequence <= toc.last_complete_session:
            current_track = track.sequence
            continue

        if toc.last_complete_session > 0:
            session_ending_track[toc.last_complete_session] = current_track

        toc.last_complete_session = track.sequence

    session_ending_track[toc.last_complete_session] = max(t.sequence for t in tracks)

    current_session = 0

    for track in sorted(tracks, key=lambda t: t.sequence):
        track_control = track_flags.get(track.sequence, 0)

        if track_control == 0 and track.tracktype != CDRDAO_TRACK_TYPE_AUDIO:
            track_control = 0x04  # Data track flag

        # Lead-Out
        if track.sequence > current_session and current_session != 0:
            leadout_amsf = lba_to_msf(track.start_sector - 150) # subtract 150 for lead-in
            leadout_pmsf = lba_to_msf(max(t.start_sector for t in tracks))

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

            leadin_pmsf = lba_to_msf(next((t.start_sector + t.sectors for t in tracks if t.sequence == ending_track_number), 0))

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

    return toc_ms.getvalue()