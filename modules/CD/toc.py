import logging
from typing import Optional, List
from enum import IntEnum
import struct

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TOC:
    MODULE_NAME = "CD TOC decoder"

    class CDTOC:
        def __init__(self):
            self.data_length: int = 0
            self.first_track: int = 0
            self.last_track: int = 0
            self.track_descriptors: List['TOC.CDTOCTrackDataDescriptor'] = []

    class CDTOCTrackDataDescriptor:
        def __init__(self):
            self.reserved1: int = 0
            self.adr: int = 0
            self.control: int = 0
            self.track_number: int = 0
            self.reserved2: int = 0
            self.track_start_address: int = 0

    class TocAdr(IntEnum):
        NoInformation = 0x00
        TrackPointer = 0x01
        VideoTrackPointer = 0x04
        ISRC = 0x03
        MediaCatalogNumber = 0x02

    class TocControl(IntEnum):
        TwoChanNoPreEmph = 0x00
        TwoChanPreEmph = 0x01
        CopyPermissionMask = 0x02
        DataTrack = 0x04
        DataTrackIncremental = 0x05
        FourChanNoPreEmph = 0x08
        FourChanPreEmph = 0x09
        ReservedMask = 0x0C

    @staticmethod
    def Decode(cd_toc_response: bytes) -> Optional[CDTOC]:
        if not cd_toc_response or len(cd_toc_response) <= 4:
            return None

        decoded = TOC.CDTOC()
        decoded.data_length = struct.unpack('>H', cd_toc_response[0:2])[0]
        decoded.first_track = cd_toc_response[2]
        decoded.last_track = cd_toc_response[3]

        decoded.track_descriptors = []

        if decoded.data_length + 2 != len(cd_toc_response):
            logger.debug(
                f"Expected CD TOC size {decoded.data_length + 2} bytes is not received size {len(cd_toc_response)} bytes, not decoding"
            )
            return None

        for i in range((decoded.data_length - 2) // 8):
            descriptor = TOC.CDTOCTrackDataDescriptor()
            offset = i * 8 + 4
            descriptor.reserved1 = cd_toc_response[offset]
            descriptor.adr = (cd_toc_response[offset + 1] & 0xF0) >> 4
            descriptor.control = cd_toc_response[offset + 1] & 0x0F
            descriptor.track_number = cd_toc_response[offset + 2]
            descriptor.reserved2 = cd_toc_response[offset + 3]
            descriptor.track_start_address = struct.unpack('>I', cd_toc_response[offset + 4:offset + 8])[0]
            decoded.track_descriptors.append(descriptor)

        return decoded

    @staticmethod
    def Prettify(cd_toc_response: Optional[CDTOC]) -> Optional[str]:
        if cd_toc_response is None:
            return None

        response = cd_toc_response
        output = []

        output.append(f"First track number in first complete session: {response.first_track}")
        output.append(f"Last track number in last complete session: {response.last_track}")

        for descriptor in response.track_descriptors:
            if descriptor.track_number == 0xAA:
                output.append("Track number: Lead-Out")
            else:
                output.append(f"Track number: {descriptor.track_number}")

            output.append(f"Track starts at LBA: {descriptor.track_start_address} or MSF: {(descriptor.track_start_address & 0x0000FF00) >> 8}:{(descriptor.track_start_address & 0x00FF0000) >> 16}:{(descriptor.track_start_address & 0xFF000000) >> 24}")

            adr = TOC.TocAdr(descriptor.adr)
            if adr == TOC.TocAdr.NoInformation:
                output.append("Q subchannel mode not given")
            elif adr == TOC.TocAdr.TrackPointer:
                output.append("Q subchannel stores track pointer")
            elif adr == TOC.TocAdr.VideoTrackPointer:
                output.append("Q subchannel stores video track pointer")
            elif adr == TOC.TocAdr.ISRC:
                output.append("Q subchannel stores ISRC")
            elif adr == TOC.TocAdr.MediaCatalogNumber:
                output.append("Q subchannel stores media catalog number")
            else:
                output.append(f"Q subchannel mode: {descriptor.adr}")

            control = TOC.TocControl(descriptor.control)
            if descriptor.control & TOC.TocControl.ReservedMask == TOC.TocControl.ReservedMask:
                output.append(f"Reserved flags {descriptor.control} set")
            else:
                if control == TOC.TocControl.TwoChanNoPreEmph:
                    output.append("Stereo audio track with no pre-emphasis")
                elif control == TOC.TocControl.TwoChanPreEmph:
                    output.append("Stereo audio track with 50/15 us pre-emphasis")
                elif control == TOC.TocControl.FourChanNoPreEmph:
                    output.append("Quadraphonic audio track with no pre-emphasis")
                elif control == TOC.TocControl.FourChanPreEmph:
                    output.append("Quadraphonic audio track with 50/15 us pre-emphasis")
                elif control == TOC.TocControl.DataTrack:
                    output.append("Data track recorded uninterrupted")
                elif control == TOC.TocControl.DataTrackIncremental:
                    output.append("Data track recorded incrementally")

                if descriptor.control & TOC.TocControl.CopyPermissionMask:
                    output.append("Digital copy of track is permitted")
                else:
                    output.append("Digital copy of track is prohibited")

            output.append("")

        return "\n".join(output)

    @staticmethod
    def Prettify_bytes(cd_toc_response: bytes) -> str:
        decoded = TOC.Decode(cd_toc_response)
        return TOC.Prettify(decoded)
