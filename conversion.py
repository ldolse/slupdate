import os
from modules.plugin_register import PluginRegister
from modules.clonecd_filter import CloneCDFilter
from modules.clonecd import CloneCD
from modules.error_number import ErrorNumber
from modules.CD.subchannel import Subchannel
from modules.CD.fulltoc import FullTOC
from modules.CD.cd_types import enum_name, SectorTagType, MediaType, MetadataMediaType, TrackType, TrackSubchannelType
from modules.checksums import CRC16CCITTContext

def initialize_plugins():
    register = PluginRegister.get_instance()
    register.register_media_image("CloneCD", CloneCDFilter)

def validate_subchannel(clonecd: CloneCD):
    print("Validating subchannel data...")
    
    if not clonecd.tracks:
        print("No tracks found. Cannot validate subchannel.")
        return
    
    first_track = clonecd.tracks[0]
    error, subchannel_data = clonecd.read_sector_tag(first_track.start_sector, SectorTagType.CdSectorSubchannel, first_track.sequence)
    
    if error != ErrorNumber.NoError or not subchannel_data:
        print(f"Failed to read subchannel data. Error: {error}")
        return
    
    if len(subchannel_data) != 96:
        print(f"Invalid subchannel data length. Expected 96 bytes, got {len(subchannel_data)} bytes.")
        return
    
    # Deinterleave subchannel (using Subchannel class method)
    deinterleaved = Subchannel.deinterleave(subchannel_data)
    
    # Check P subchannel (should be all 0xFF for lead-in)
    p_subchannel = deinterleaved[:12]
    if all(b == 0xFF for b in p_subchannel):
        print("P subchannel validated successfully (all 0xFF for lead-in).")
    else:
        print(f"P subchannel validation failed. Expected all 0xFF, got: {p_subchannel.hex()}")
    
    # Check Q subchannel structure
    q_subchannel = deinterleaved[12:24]
    print(f"Q subchannel data: {q_subchannel.hex()}")
    
    # Use Subchannel.prettify_q method to decode and display Q subchannel information
    q_info = Subchannel.prettify_q(q_subchannel, True, first_track.start_sector, False, True, False)
    print("Q subchannel decoded:")
    print(q_info)
    
    # Calculate CRC
    calculated_crc = CRC16CCITTContext.calculate(q_subchannel[:10])
    stored_crc = (q_subchannel[10] << 8) | q_subchannel[11]
    print(f"Stored CRC: {stored_crc:04X}")
    print(f"Calculated CRC: {calculated_crc:04X}")
    
    if calculated_crc == stored_crc:
        print("Q subchannel CRC is valid.")
    else:
        print(f"Q subchannel CRC is invalid. Expected {stored_crc:04X}, calculated {calculated_crc:04X}")

def get_track_type(control: int) -> str:
    if control & 0x04:
        return "Data track, recorded uninterrupted"
    elif control & 0x01:
        return "Stereo audio track with pre-emphasis"
    else:
        return "Stereo audio track with no pre-emphasis"

def print_image_info(clonecd: CloneCD):
    print(f"Image format identified by {clonecd.name} ({clonecd.id}).\n")

    print(f"{clonecd._image_info.media_type} image describes a disc of type {clonecd._image_info.media_type}")
    print("Image information:")
    print(f"Format: {clonecd.format}")
    print(f"Image without headers is {clonecd._image_info.image_size} bytes long")
    print(f"Contains a media of {clonecd._image_info.sectors} sectors with a maximum sector size of {clonecd._image_info.sector_size} bytes (if all sectors are of the same size this would be {clonecd._image_info.sectors * clonecd._image_info.sector_size} bytes)")
    print(f"Created on {clonecd._image_info.creation_time}")
    print(f"Last modified on {clonecd._image_info.last_modification_time}")
    print(f"Contains a media of type {enum_name(MediaType, clonecd._image_info.media_type)} and XML type {enum_name(MetadataMediaType, clonecd._image_info.metadata_media_type)}")
    print(f"Has partitions: {'Yes' if clonecd._image_info.has_partitions else 'No'}")
    print(f"Has sessions: {'Yes' if clonecd._image_info.has_sessions else 'No'}")
    print("Contains {} readable sector tags:".format(len(clonecd._image_info.readable_sector_tags)))
    print(" ".join(enum_name(SectorTagType, tag) for tag in clonecd._image_info.readable_sector_tags))

    if clonecd._full_toc:
        print("\nCompactDisc Table of Contents contained in image:")
        toc = FullTOC.decode(clonecd._full_toc)
        if toc:
            print(f"First complete session number: {toc.first_complete_session}")
            print(f"Last complete session number: {toc.last_complete_session}")
            
            current_session = 0
            for descriptor in toc.track_descriptors:
                if descriptor.session_number != current_session:
                    print(f"Session {descriptor.session_number}")
                    current_session = descriptor.session_number

                if descriptor.point == 0xA0:
                    print(f"First track number: {descriptor.pmin} ({get_track_type(descriptor.control)})")
                    print(f"Disc type: {descriptor.psec}")
                elif descriptor.point == 0xA1:
                    print(f"Last track number: {descriptor.pmin} ({get_track_type(descriptor.control)})")
                elif descriptor.point == 0xA2:
                    print(f"Lead-out start position: {descriptor.pmin:02d}:{descriptor.psec:02d}:{descriptor.pframe:02d}")
                    print(f"Lead-out is {'audio' if (descriptor.control & 0x04) == 0 else 'data'} type")
                elif 1 <= descriptor.point <= 99:
                    track_type = "Data" if (descriptor.control & 0x04) else "Audio"
                    print(f"{track_type} track {descriptor.point} starts at: {descriptor.pmin:02d}:{descriptor.psec:02d}:{descriptor.pframe:02d} ({get_track_type(descriptor.control)})")


    print("\nImage sessions:")
    print("Session  First track  Last track  Start       End")
    print("=========================================================")
    for session in clonecd.sessions:
        print(f"{session.sequence:<9}{session.start_track:<13}{session.end_track:<12}{session.start_sector:<12}{session.end_sector}")

    print("\nImage tracks:")
    print("Track  Type             Bps   Raw bps Subchannel  Pregap  Start       End")
    print("=================================================================================")
    for track in clonecd.tracks:
        print(f"{track.sequence:<7}{enum_name(TrackType, track.type):<17}{track.bytes_per_sector:<6}{track.raw_bytes_per_sector:<8}{enum_name(TrackSubchannelType, track.subchannel_type):<12}{track.pregap:<8}{track.start_sector:<12}{track.end_sector}")
    print("\nTrack indexes:")
    print("Track  Index  Start")
    print("=======================")
    for track in clonecd.tracks:
        for index, start in track.indexes.items():
            print(f"{track.sequence:<7}{index:<7}{start}")

def main():
    initialize_plugins()
    register = PluginRegister.get_instance()

    # Path to your test file
    input_path = "Space Debris (Europe).ccd"

    # Get the filter for CloneCD
    input_filter = register.get_filter(input_path)

    if input_filter:
        print(f"Input format: {input_filter.name}")
        
        clonecd = CloneCD()

        try:
            if clonecd.identify(input_filter):
                print("CloneCD image identified successfully.")

                error = clonecd.open(input_filter)
                if error == ErrorNumber.NoError:
                    print("CloneCD image opened successfully.")
                    
                    # Print some basic information about the image
                    print(f"Number of tracks: {len(clonecd.tracks)}")
                    print(f"Number of sessions: {len(clonecd.sessions)}")
                    print(f"Media type: {clonecd._image_info.media_type}")

                    # Try to read the first sector of the first track
                    if clonecd.tracks:
                        first_track = clonecd.tracks[0]
                        error, sector_data = clonecd.read_sector(first_track.start_sector, first_track.sequence)
                        if error == ErrorNumber.NoError:
                            print(f"Successfully read first sector of track 1. First 16 bytes: {sector_data[:16].hex()}")
                        else:
                            print(f"Failed to read first sector of track 1. Error: {error}")

                    # Validate subchannel data
                    validate_subchannel(clonecd)
                    
                    # Print image information
                    print_image_info(clonecd)

                else:
                    print(f"Failed to open CloneCD image. Error: {error}")
            else:
                print("Failed to identify CloneCD image.")
        finally:
            clonecd.close()
    else:
        print("Unsupported input format")

if __name__ == "__main__":
    main()