import struct
import math

# CRC-16 Table
CRC16_TAB = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7, 
    0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef, 
    0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6, 
    0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de, 
    0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485, 
    0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d, 
    0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4, 
    0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc, 
    0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823, 
    0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b, 
    0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12, 
    0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a, 
    0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41, 
    0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49, 
    0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70, 
    0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78, 
    0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f, 
    0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067, 
    0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e, 
    0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256, 
    0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d, 
    0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405, 
    0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c, 
    0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634, 
    0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab, 
    0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3, 
    0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a, 
    0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92, 
    0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9, 
    0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1, 
    0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8, 
    0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
]

def crc16(buf):
    cksum = 0
    for b in buf:
        cksum = CRC16_TAB[((cksum >> 8) ^ b) & 0xFF] ^ (cksum << 8)
    return ~cksum & 0xFFFF

def itob(val):
    return ((val // 10) << 4) + (val % 10)
    
def number_to_hex_msf(number):
    # Convert the number to BCD (Binary-Coded Decimal)
    return ((number // 10) << 4) + (number % 10)

def create_sub_channel(filename, str_sectors):
    try:
        sectors = int(str_sectors)
    except ValueError:
        print("Wrong size!")
        return

    if sectors <= 0:
        print("Wrong size!")
        return

    try:
        subchannel = open(filename, "wb+")
    except OSError as e:
        print(f"Error opening file {filename}: {e}")
        return

    print(f"File: {filename}")
    print(f"Size (bytes): {sectors * 96}")
    print(f"Size (sectors): {sectors}")

    buffer = bytearray(10)
    buffer[0] = 0x41
    buffer[1] = 0x01
    buffer[2] = 0x01
    buffer[6] = 0x00

    for sector in range(sectors):
        sector2 = sector + 150

        mindbl = sector / 60 / 75
        min = math.floor(mindbl)
        secdbl = (sector - (min * 60 * 75)) / 75
        sec = math.floor(secdbl)
        frame = sector - (min * 60 * 75) - (sec * 75)
        buffer[3] = itob(min)
        buffer[4] = itob(sec)
        buffer[5] = itob(frame)

        mindbl = sector2 / 60 / 75
        min = math.floor(mindbl)
        secdbl = (sector2 - (min * 60 * 75)) / 75
        sec = math.floor(secdbl)
        frame = sector2 - (min * 60 * 75) - (sec * 75)
        buffer[7] = itob(min)
        buffer[8] = itob(sec)
        buffer[9] = itob(frame)

        crc = crc16(buffer)
        crc_bytes = struct.pack('>H', crc)

        subchannel.write(bytearray(12))  # 12 zero bytes
        subchannel.write(buffer)
        subchannel.write(crc_bytes)
        subchannel.write(bytearray(72))  # 72 zero bytes

        print(f"Creating: {int((100 * sector) / sectors):02d}%\r", end='')

    subchannel.seek(0)
    subchannel.write(bytearray([0xFF] * 12))  # 12 FF bytes at the start
    print("Creating: 100%")
    subchannel.close()
    print("Done!")

def sector_to_sub_offset(sector):
	# .SUB files have 96 bytes in each sector, with a 12 byte FF'd header at the beginning.
	# Subtracting 150 is for the 2 second lead-in they have, for whatever reason.
	# http://forum.imgburn.com/index.php?/topic/2122-how-to-convert-mmssff-to-bytes/&do=findComment&comment=25842
    # Convert a sector to a byte offset for a .SUB file
    return (sector - 150) * 96 + 12

    
def lsd_to_sub(lsd_path, sub_path, cue):
    from modules.toc import MSFToSector
    try:
        # Read the SUB file as a bytearray
        with open(sub_path, "rb") as sub_file:
            sub = bytearray(sub_file.read())
        
        with open(lsd_path, "rb") as lsd_file:
            while True:
                # Next 3 bytes are the MSF. For some reason the true number is stored in raw HEX.
                msf_bytes = lsd_file.read(3)
                if not msf_bytes or len(msf_bytes) < 3:
                    break
                
                lsd_minutes = int(f"{msf_bytes[0]:02X}")
                lsd_seconds = int(f"{msf_bytes[1]:02X}")
                lsd_frames = int(f"{msf_bytes[2]:02X}")

                # Convert MSF to sector
                sector_msf = MSFToSector(lsd_minutes, lsd_seconds, lsd_frames)
                # Get the offset in the SUB file
                replace_offset = sector_to_sub_offset(sector_msf)

                # Read the next 12 bytes for replacement
                replacement_bytes = lsd_file.read(12)
                if len(replacement_bytes) < 12:
                    break
                
                for i in range(12):
                    sub[replace_offset + i] = replacement_bytes[i]

                #print(f"Replaced 12 byte subchannel at MSF: {lsd_minutes}:{lsd_seconds}:{lsd_frames} (sector: {sector_msf}) at offset: {replace_offset:#X}")
                print(f"Replaced 12 byte subchannel at MSF: {lsd_minutes}:{lsd_seconds}:{lsd_frames} (sector: {sector_msf}) at offset: {replace_offset}")


        # Generate subchannel data for CDDA tracks
        gen_sub_cdda(sub, cue)
        print("Finished LSD -> Patching!")
        
        # Write the modified sub array back to the file
        with open(sub_path, "wb") as sub_file:
            sub_file.write(sub)

    except FileNotFoundError:
        raise RuntimeError("Not a valid LSD file.")
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")


def gen_sub_cdda(sub, cue):
    # test
    from modules.toc import SectorToMSF
    bad_byte = '0x1522f1'
    total_tracks = cue.CountCDDA()
    if total_tracks > 0:
        print(f"Adding CD Audio track data to subchannel, {total_tracks} Tracks")
        
        for cue_file in cue.List:
            print("iterating through Cue Loop")
            print(f'{cue_file.TrackType} cue track, Track:{cue_file.Track}, Index:{cue_file.Index}, Sector:{cue_file.Sector}')
            if cue_file.TrackType == "AUDIO" and cue_file.Track == 2 and cue_file.Index == 1:
                replace_offset = sector_to_sub_offset(cue_file.Sector)
                print(f'replace_offset is {replace_offset}')
        
        for cdda_track_id in range(2, total_tracks + 2):
            print(f"Adding '2 second lead-in' for Track: {cdda_track_id}")
            for i in range(150):
                countdown = 150 - i
                print(f'countdown is {countdown}')
                countdown_msf = SectorToMSF(countdown)
                print(f'countdown_msf is minutes:{countdown_msf[0]}, seconds:{countdown_msf[1]}, frames:{countdown_msf[2]}')
                binary_seconds = countdown_msf[1]
                binary_frames = countdown_msf[2]
                qsub = bytearray(10)
                
                #print(f'HexMSF CDDA_TrackID is {number_to_hex_msf(cdda_track_id)}')
                # Change the QSUB header, XxxCD means countdown
				# [01] [TrackID] [00] [MinCD] [SecCD] [FraCD] [00] [Minutes] [Seconds] [Frame] [CRC16]-[CRC16]
                sub[replace_offset + (i * 96)] = 1
                sub[replace_offset + (i * 96) + 1] = number_to_hex_msf(cdda_track_id) # Track
                sub[replace_offset + (i * 96) + 2] = 0
                sub[replace_offset + (i * 96) + 3] = 0 # MinCD, Eh just put zero, the leadin will never have minutes
                sub[replace_offset + (i * 96) + 4] = number_to_hex_msf(binary_seconds) # SecCD, Seconds Countdown
                sub[replace_offset + (i * 96) + 5] = number_to_hex_msf(binary_frames) # FraCD, Frames Countdown
                
                qsub[:10] = sub[replace_offset + (i * 96):replace_offset + (i * 96) + 10]
                
                sub_crc16 = crc16(qsub)
                sub_crca = sub_crc16 >> 8
                sub_crcb = sub_crc16 - (sub_crca << 8)
                
                sub[replace_offset + (i * 96) + 10] = sub_crca
                sub[replace_offset + (i * 96) + 11] = sub_crcb
            
            # Alright, lets add actual CD Audio track data to the subchanel
            replace_offset += (150 * 96) # Start on the part after the leadin
            print(f"Adding timecode data for Track: {cdda_track_id}, replace_offset is {replace_offset}")
            #Lets get the important tracks, so we can calculate the size after
            for cue_file in cue.List:
                if cue_file.TrackType == "AUDIO":
                    if cue_file.Track == cdda_track_id and cue_file.Index == 1: # If it = CurrentTrack Index 1
                        track_a = cue_file
                        print(f'Matched TrackA, sector is {track_a.Sector}')
                    elif cue_file.Track == cdda_track_id + 1 and cue_file.Index == 0: #If it = the one after the Current Track at Index 0
                        track_b = cue_file
                        print(f'Matched TrackA, sector is {track_b.Sector}')
            
            if cdda_track_id < total_tracks + 1:
                sector_size = track_b.Sector - track_a.Sector
                print(f'Total tracks greater than CDDA_TrackID, SectorSize is {sector_size}')
            else:
                sector_size = (len(sub) // 96 - track_a.Sector)
                print(f'Total tracks is less than cdda_track_id - calculating sector size by dividing sub by 96, SectorSize is {sector_size}')
                
            # single line way to do the above, can reinstate after troubleshooting
            #sector_size = (track_b.Sector - track_a.Sector) if cdda_track_id < total_tracks + 1 else (len(sub) // 96 - track_a.Sector)
    
            for i in range(sector_size):
                print('bad_byte in timecode loop') if hex(replace_offset + (i * 96)) == bad_byte else print('',end='')
                sub[replace_offset + (i * 96)] = 1
                sub[replace_offset + (i * 96) + 1] = number_to_hex_msf(cdda_track_id)
                sub[replace_offset + (i * 96) + 2] = 1
                
                msf = SectorToMSF(i)
                sub[replace_offset + (i * 96) + 3] = number_to_hex_msf(msf[0])
                sub[replace_offset + (i * 96) + 4] = number_to_hex_msf(msf[1])
                sub[replace_offset + (i * 96) + 5] = number_to_hex_msf(msf[2])
                
                qsub[:10] = sub[replace_offset + (i * 96):replace_offset + (i * 96) + 10]
                
                sub_crc16 = crc16(qsub)
                sub_crca = sub_crc16 >> 8
                sub_crcb = sub_crc16 - (sub_crca << 8)
                
                sub[replace_offset + (i * 96) + 10] = sub_crca
                sub[replace_offset + (i * 96) + 11] = sub_crcb

            # Move the ReplaceOffset position
            replace_offset += sector_size * 96
            print(f"replace_offset is {replace_offset}")
        
        print("Finished adding CD Audio subchannel data!")

