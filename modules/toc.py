import os
import shutil
import struct
from math import floor

def MSFToSector(Min, Sec, Fra):
    return (Min * 60 * 75) + (Sec * 75) + Fra

def SectorToMSF(Sector):
    Min = Sector // (60 * 75)
    Sector = Sector - (Min * 60 * 75)
    Sec = Sector // 75
    Sector = Sector - (Sec * 75)
    Fra = Sector
    return [Min, Sec, Fra]

def GetSectorsBySize(FileSize):
    return FileSize // 2352

def NumberToStrMSF(Number):
    HexStr = ""
    if Number <= 9:
        HexStr = HexStr + "0" + str(Number)
    else:
        HexStr = HexStr + str(Number)
    return HexStr
    
# Table of CRC constants - implements x^16+x^12+x^5+1
crc16_tab = [0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7, 
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
             0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0]

def crc16(data, len):
    cksum = 0
    for i in range(len):
        cksum = crc16_tab[((cksum >> 8) ^ data[i]) & 0xFF] ^ (cksum << 8)
    return ~cksum

# Sub function
def sub(filename, strsectors):
    sectors = int(strsectors)
    if sectors == 0 or sectors == -1:
        print("Wrong size!")
        return

    with open(filename, "w+b") as subchannel:
        buffer = bytearray([0x41, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        for sector in range(sectors):
            mindbl = sector / 60 / 75
            minutes = int(floor(mindbl))
            secdbl = (sector - (minutes * 60 * 75)) / 75
            sec = int(floor(secdbl))
            frame = sector - (minutes * 60 * 75) - (sec * 75)
            buffer[3] = int(minutes)
            buffer[4] = int(sec)
            buffer[5] = int(frame)

            mindbl = sector2 / 60 / 75
            minutes = int(floor(mindbl))
            secdbl = (sector2 - (minutes * 60 * 75)) / 75
            sec = int(floor(secdbl))
            frame = sector2 - (minutes * 60 * 75) - (sec * 75)
            buffer[7] = int(minutes)
            buffer[8] = int(sec)
            buffer[9] = int(frame)

            crc = crc16(buffer, 10)

            for i in range(12):
                subchannel.write(b"\x00")
            subchannel.write(buffer)
            subchannel.write(struct.pack("B", crc[1]))
            subchannel.write(struct.pack("B", crc))
            for i in range(72):
                subchannel.write(b"\x00")

            print("Creating: %02u%%" % ((100 * sector) / sectors))
    subchannel.seek(0, 0)
    for i in range(12):
        subchannel.write(b"\xFF")
    print("Creating: 100%%")
    subchannel.close()
    print("Done!")
    return

def sub_new(filename, strsectors):
    with open(filename, 'wb') as subchannel:
        sectors = int(strsectors)
        sector2s = [150 + i for i in range(sectors)]
        if sectors == 0 or sectors == -1:
            print('Wrong size!')
            return

        buffer = bytearray(10)
        buffer[0] = 0x41
        buffer[1] = 0x01
        buffer[2] = 0x01
        buffer[6] = 0x00

        for sector, sector2 in zip(range(sectors), sector2s):
            mindbl = sector / 60 / 75
            minutes = int(floor(mindbl))
            secdbl = (sector - (minutes * 60 * 75)) / 75
            sec = int(floor(secdbl))
            frame = sector - (minutes * 60 * 75) - (sec * 75)
            buffer[3] = int(minutes)
            buffer[4] = int(sec)
            buffer[5] = int(frame)

            mindbl = sector2 / 60 / 75
            minutes = int(floor(mindbl))
            secdbl = (sector2 - (minutes * 60 * 75)) / 75
            sec = int(floor(secdbl))
            frame = sector2 - (minutes * 60 * 75) - (sec * 75)
            buffer[7] = int(minutes)
            buffer[8] = int(sec)
            buffer[9] = int(frame)

            crc = crc16(buffer, 10)
            # Write the checksum into the subchannel
            for i in range(12):
                subchannel.write(bytes([0x00]))
            subchannel.write(buffer)
            subchannel.write(bytes([(crc >> 8) & 0xff, (crc >> 0) & 0xff]))
            for i in range(72):
                subchannel.write(bytes([0x00]))

            print("Creating: %02u%%" % ((100 * sector) / sectors))
        subchannel.seek(0, 0)
        for i in range(12):
            subchannel.write(b"\xFF")
        print("Creating: 100%%")
        subchannel.close()
    print('Done!')


def ccd_Generator(cue):
    # Use GetBinPath in class
    BaseName = cue.GetBinPath(cue.FDRPath)

    # Useful CUE information we'll use below
    # Get total track count
    TrackCount = cue.CountCDDA(True)
    # Get audio track count
    TrackCountCDDA = cue.CountCDDA()
    TotalMSFLeadin = SectorToMSF(cue.MultiSectorCount + 150)
    # Let's make an export folder
    print(f"Exporting to: 'CCD"+os.sep+"{BaseName}.SUB'.")
    if not os.path.exists("CCD"):
        os.makedirs("CCD")
        print("Directory 'CCD' doesn't exist! Creating...")

    if not os.path.exists(f"CCD{os.sep}{BaseName}"):
        os.makedirs(f"CCD{os.sep}{BaseName}")
        print(f"Directory 'CCD{os.sep}{BaseName}' doesn't exist! Creating...")
    print("Creating CCD file")
    with open(f"CCD{os.sep}{BaseName}{os.sep}{BaseName}.ccd", 'w') as CCDFile:
        # Control string based on audio tracks
        Control = "Control=0x04"
        if TrackCountCDDA > 0:
            Control = "Control=0x00"

        # Writing CCD headers
        print("Writing CCD headers")
        CCDFile.write("[CloneCD]\n")
        CCDFile.write("Version=3\n")
        CCDFile.write("[Disc]\n")
        CCDFile.write(f"TocEntries={3 + TrackCount}\n")
        CCDFile.write("Sessions=1\n")
        CCDFile.write("DataTracksScrambled=0\n")
        CCDFile.write("CDTextLength=0\n")
        CCDFile.write("[Session 1]\n")
        CCDFile.write("PreGapMode=2\n")
        CCDFile.write("PreGapSubC=1\n")

        # Writing CCD Entries
        print("Writing CCD Entries")
        CCDFile.write("[Entry 0]\n")
        CCDFile.write("Session=1\n")
        CCDFile.write("Point=0xa0\n")
        CCDFile.write("ADR=0x01\n")
        CCDFile.write("Control=0x04\n")
        CCDFile.write("TrackNo=0\n")
        CCDFile.write("AMin=0\n")
        CCDFile.write("ASec=0\n")
        CCDFile.write("AFrame=0\n")
        CCDFile.write("ALBA=-150\n")
        CCDFile.write("Zero=0\n")
        CCDFile.write("PMin=1\n")
        CCDFile.write("PSec=32\n")
        CCDFile.write("PFrame=0\n")
        CCDFile.write("PLBA=6750\n")

        # Entry 1
        CCDFile.write("[Entry 1]\n")
        CCDFile.write("Session=1\n")
        CCDFile.write("Point=0xa1\n")
        CCDFile.write("ADR=0x01\n")
        CCDFile.write(f"{Control}\n")
        CCDFile.write("TrackNo=0\n")
        CCDFile.write("AMin=0\n")
        CCDFile.write("ASec=0\n")
        CCDFile.write("AFrame=0\n")
        CCDFile.write("ALBA=-150\n")
        CCDFile.write("Zero=0\n")
        CCDFile.write(f"PMin={TrackCount}\n")
        CCDFile.write("PSec=0\n")
        CCDFile.write("PFrame=0\n")
        CCDFile.write(f"PLBA={MSFToSector(TrackCount, 0, 0) - 150}\n")

        # Entry 2
        CCDFile.write("[Entry 2]\n")
        CCDFile.write("Session=1\n")
        CCDFile.write("Point=0xa2\n")
        CCDFile.write("ADR=0x01\n")
        CCDFile.write(f"{Control}\n")
        CCDFile.write("TrackNo=0\n")
        CCDFile.write("AMin=0\n")
        CCDFile.write("ASec=0\n")
        CCDFile.write("AFrame=0\n")
        CCDFile.write("ALBA=-150\n")
        CCDFile.write("Zero=0\n")
        CCDFile.write(f"PMin={TotalMSFLeadin[0]}\n")
        CCDFile.write(f"PSec={TotalMSFLeadin[1]}\n")
        CCDFile.write(f"PFrame={TotalMSFLeadin[2]}\n")
        CCDFile.write(f"PLBA={cue.MultiSectorCount}\n")

        # Loop through all the audio tracks
        CurrentEntry = 3
        for CueFile in cue.List:
            if CueFile.Index == 1:
                CCDFile.write(f"[Entry {CurrentEntry}]\n")
                CCDFile.write("Session=1\n")
                CCDFile.write(f"Point=0x{(CurrentEntry - 2):02x}\n")
                CCDFile.write("ADR=0x01\n")
                if CueFile.TrackType == "AUDIO":
                    CCDFile.write("Control=0x00\n")
                else:
                    CCDFile.write("Control=0x04\n")
                CCDFile.write("TrackNo=0\n")
                CCDFile.write("AMin=0\n")
                CCDFile.write("ASec=0\n")
                CCDFile.write("AFrame=0\n")
                CCDFile.write("ALBA=-150\n")
                CCDFile.write("Zero=0\n")
                
                EntryMSF = SectorToMSF(CueFile.Sector + 150)
                if CueFile.Sector > 150 and CueFile.TrackType == "MODE2/2352":
                    EntryMSF = SectorToMSF(CueFile.Sector)
                    CCDFile.write(f"PMin={EntryMSF[0]}\n")
                    CCDFile.write(f"PSec={EntryMSF[1]}\n")
                    CCDFile.write(f"PFrame={EntryMSF[2]}\n")
                    CCDFile.write(f"PLBA={CueFile.Sector - 150}\n")
                else:
                    CCDFile.write(f"PMin={EntryMSF[0]}\n")
                    CCDFile.write(f"PSec={EntryMSF[1]}\n")
                    CCDFile.write(f"PFrame={EntryMSF[2]}\n")
                    CCDFile.write(f"PLBA={CueFile.Sector}\n")
                CurrentEntry += 1

        # Writing TRACK info
        print("Writing TRACK info")
        CurrentTrack = 0
        for CueFile in cue.List:
            if CueFile.Track != CurrentTrack:
                CurrentTrack = CueFile.Track
                CCDFile.write(f"[TRACK {CurrentTrack}]\n")
                if CueFile.TrackType == "AUDIO":
                    CCDFile.write("MODE=0\n")
                else:
                    CCDFile.write("MODE=2\n")
            if CueFile.TrackType == "MODE2/2352":
                if CueFile.Sector > 150:
                    CCDFile.write(f"INDEX {CueFile.Index}={CueFile.Sector - 150}\n")
                else:
                    CCDFile.write(f"INDEX {CueFile.Index}={CueFile.Sector}\n")
            else:
                CCDFile.write(f"INDEX {CueFile.Index}={CueFile.Sector}\n")

    print("Done writing CCD!")
    

def handle_image(cue):
    # Use GetBinPath in class
    BaseName = cue.GetBinPath(cue.FDRPath)
    # Merge or copy the image based on the track type
    if cue.IsMultiTrack:
        print("Merging image (This will take a moment)")
        cue.MergeImage(f"CCD{os.sep}{BaseName}{os.sep}{BaseName}.img")
    else:
        print("Copying image (This will take a moment)")
        shutil.copyfile(cue.BinPath + cue.BinaryFN, f"CCD{os.sep}{BaseName}{os.sep}{BaseName}.img")
    print("Image handling complete")
    
def export_cue(cue):
    base_name = cue.GetBinPath(cue.FDRPath)
    print("Creating modified CUE")
    cue_path = os.path.join("CCD", base_name, f"{base_name}.cue")
    img_file = f"{base_name}.img"
    cue.ExportCue(cue_path, img_file)
    print("Done writing CUE!")

class CUE:
    List = []
    BinaryFN = ""
    BinPath = ""
    IsMultiTrack = False
    FDRPath = []
    MultiSectorCount = 0  # Total sectors counted for multiple sector tracks

    def __init__(self):
        """Initialize a new CUE object with default values."""
        self.Track = 0
        self.TrackType = ""
        self.Index = 0
        self.TrackFN = ""
        self.MSF = [0, 0, 0]
        self.Sector = 0

    # Add a track index
    def AddListing(self, Track, TrackType, Index, Minutes, Seconds, Frames, FileName):
        """Add a track index to the CUE list.
        
        Args:
            Track (int): Track number.
            TrackType (str): Track type (e.g., "AUDIO").
            Index (int): Index number.
            Minutes (int): Minutes part of the MSF.
            Seconds (int): Seconds part of the MSF.
            Frames (int): Frames part of the MSF.
            FileName (str): File name of the track.
        """
        CUETrack = CUE()
        CUETrack.Track = Track
        CUETrack.TrackType = TrackType
        CUETrack.Index = Index
        CUETrack.TrackFN = FileName
        CUETrack.Sector = MSFToSector(Minutes, Seconds, Frames)

        # Alright, lets get the path of the CUE/Bin file(s)
        TrackPath = ""
        for x in range(len(CUE.FDRPath) - 2):  # Take 1 so it doesn't overflow, take another 1 to get rid of the CUE filename in this path
            TrackPath += CUE.FDRPath[x] + os.sep
            print(f'TrackPath is {TrackPath}')

        # handle multi track redump cue files
        if CUE.IsMultiTrack:
            # BIN file exists?
            if not os.path.isfile(TrackPath + FileName):
                raise RuntimeError(f"BIN Track '{TrackPath + FileName}' is missing!")
            if not os.path.isfile(TrackPath + CUE.BinaryFN):
                raise RuntimeError(f"BIN Track '{TrackPath + CUE.BinaryFN}' is missing!")  # Check for Track 1

            # Start counting!
            if Index == 0:
                CUETrack.Sector = CUE.MultiSectorCount
                print("Index 0, MultiSectorCount is: "+str(CUE.MultiSectorCount))
            elif Index == 1:
                CUETrack.Sector = CUE.MultiSectorCount + 150  # 2 Second LeadIn on Index 1's
                print("Index 1 pregap, MultiSectorCount is: "+str(CUE.MultiSectorCount))
                # Add the sector count of the next track
                CUE.MultiSectorCount += GetSectorsBySize(int(os.path.getsize(TrackPath + FileName)))
                print("Index 1, sectors from "+FileName+" MultiSectorCount is: "+str(CUE.MultiSectorCount))
            else:  # Umm, Index 3? uhhhh
                raise RuntimeError("Invalid Index in CUE!")
            # Recalculate MSF
            CUETrack.MSF = SectorToMSF(CUETrack.Sector)
        else:  # Single track BIN
            CUETrack.MSF[0] = Minutes
            CUETrack.MSF[1] = Seconds
            CUETrack.MSF[2] = Frames

            # Alrighty so because the IsMultiTrack function only changes when it sees more than 1 FILE parameter, we better count the sectors of Track 1!
            # But if it can't find it, ignore it. We'll also add the sector count here
            if os.path.isfile(TrackPath + CUE.BinaryFN):
                CUE.MultiSectorCount = GetSectorsBySize(int(os.path.getsize(TrackPath + CUE.BinaryFN)))
                print("Index 1, sectors from "+CUE.BinaryFN+" MultiSectorCount is: "+str(CUE.MultiSectorCount))
            else:
                print(f"Couldn't find {CUE.BinaryFN}")

        CUE.List.append(CUETrack)

    def AddCue(self, CuePath):
        """Parse and add tracks from a CUE file.
        
        Args:
            CuePath (str): Path to the CUE file.
        """
        # Open the file, fix the slashes
        CuePath = CuePath.replace("/", os.sep)
        # Set the path and read the CUE
        CUE.FDRPath = CuePath.split(os.sep)
        
        try:
            with open(CuePath, "r") as CueFile:
                CurrentTrack = 0
                CurrentTrackType = ""
                CurrentTrackFN = ""

                if CueFile.read(1) == '\x00':
                    raise RuntimeError("This doesn't seem to be a cue file!")
                else:
                    CueFile.seek(0)  # Go back to the start.

                for line in CueFile:
                    Line = line.strip()

                    # This is the header
                    if Line.startswith("FILE"):
                        # Is a standard single track BIN file (or the first file in a multi-track)
                        if CUE.BinaryFN == "":
                            print(f'Processing the single track or first track in the cue class - line value: {line}')
                            Split = Line.split('"')  # Split the quotes
                            CUE.BinaryFN = Split[1]  # Set the filename the CUE links to in our global
                            print(f"CUE.BinaryFN is {CUE.BinaryFN}")
                            CurrentTrackFN = Split[1]  # Add it to the array afterwards
                        else:  # Oh ok so it's one of THOSE multi bin ones, nice. Lets fix it.
                            print(f'Processing the multi track mode in the cue class - Line: {Line}')
                            Split = Line.split('"')  # Split the quotes
                            CurrentTrackFN = Split[1]  # Add it to the array afterwards
                            # Oooh this is a separated track image!
                            if not CUE.IsMultiTrack:
                                CUE.IsMultiTrack = True
                                print("Split Track CUE image detected")
                    elif Line.startswith("TRACK"):
                        Split = Line.replace("  ", " ").split(" ")  # Split the spaces, get rid of most duplicate spaces if there are any
                        # Set the current track and track type for when the next loop happens
                        CurrentTrack = int(Split[1])
                        CurrentTrackType = Split[2]
                    elif Line.startswith("INDEX"):
                        Split = Line.split(" ")  # Split the spaces
                        MSF = Split[2].split(":")  # Split the colons from the MSF XX:XX:XX

                        # QUICK HACK TO ADDRESS ISSUE #4 ON GITHUB
                        # Ok so is there an Index of 1, with 00 00 00 MSF?
                        # Hmm this COULD be a bad redump.org cuesheet.
                        # If there's a missing Index 00 then it's def bad, lets check for it
                        if CurrentTrackType == "AUDIO" and int(Split[1]) == 1 and int(MSF[0]) == 0 and int(MSF[1]) == 0 and int(MSF[2]) == 0:
                            # We'll default the exists flag to false, because the FOR loop won't do anything if it's not found
                            Index0Exists = False
                            for IndexFixCue in CUE.List:
                                if IndexFixCue.Index == 0 and IndexFixCue.Track == CurrentTrack and IndexFixCue.TrackType == CurrentTrackType:
                                    # Ok there was an index of 00 beforehand for this track
                                    Index0Exists = True

                            # Hmmm, guess I was wrong and there's no leadin or something for this track?
                            if Index0Exists:
                                self.AddListing(CurrentTrack, CurrentTrackType, int(Split[1]), int(MSF[0]), int(MSF[1]), int(MSF[2]), CurrentTrackFN)
                            else:  # Ok confirmed, this is a bad cuesheet. Let's fix it ourselves
                                print(f"WARNING! Bad Index in CueSheet for TRACK '{CurrentTrack}'! Repairing...")
                                print("If it's a ReDump.org source, you should report the cuesheet!")
                                self.AddListing(CurrentTrack, CurrentTrackType, 0, 0, 0, 0, CurrentTrackFN)
                                self.AddListing(CurrentTrack, CurrentTrackType, 1, 0, 2, 0, CurrentTrackFN)
                        else:
                            self.AddListing(CurrentTrack, CurrentTrackType, int(Split[1]), int(MSF[0]), int(MSF[1]), int(MSF[2]), CurrentTrackFN)
        except FileNotFoundError:
            raise RuntimeError(".CUE file doesn't exist!")

    def ListTracks(self):
        """List all tracks and their filenames."""
        if not CUE.FDRPath:
            raise RuntimeError("FDRPath is not populated.")
        
        print(f"Tracks found in CUE: {len(CUE.List)}")
        for track in CUE.List:
            print(f"Track: {track.Track}, Type: {track.TrackType}, Index: {track.Index}, Filename: {track.TrackFN}")

        print(f"FDRPath: {'/'.join(CUE.FDRPath)}")


    def CountCDDA(self, CountData=False):
        """Counts all the tracks, excluding the data tracks by default"""
        TrackCount = 0
        for CueFile in CUE.List:
            if CueFile.Index == 0:
                TrackCount += 1
            elif CountData:
                if CueFile.Index == 1 and CueFile.TrackType == "MODE2/2352":
                    TrackCount += 1
        return TrackCount

    def MergeImage(self, ExportPath):
        with open(ExportPath, "wb") as MergedImage:
            TrackNum = 1
            for CueFile in CUE.List:
                if CueFile.Index == 1:
                    # Get the path of the bin file(s)
                    TrackPath = ""
                    for x in range(len(CUE.FDRPath) - 2):  # Take 1 so it doesn't overflow, take another to remove the CUE filename in this path
                        TrackPath += CUE.FDRPath[x] + os.sep

                    # Verification to check the track numbers are correct
                    if CueFile.Track == TrackNum:
                        print(f"Stitching '{CueFile.TrackFN}'.")
                        if not os.path.isfile(TrackPath + CueFile.TrackFN):
                            raise RuntimeError(f"BIN Track '{TrackPath + CueFile.TrackFN}' is missing!")
                        with open(TrackPath + CueFile.TrackFN, "rb") as ImageTrack:
                            MergedImage.write(ImageTrack.read())
                    else:
                        for OrderedCueFile in CUE.List:
                            if OrderedCueFile.Index == 1 and OrderedCueFile.Track == TrackNum:
                                print("Warning! CUE sheet is out of order!")
                                print(f"Expected Track: {TrackNum}, got Track: {CueFile.Track} instead!")
                                print(f"Stitching '{OrderedCueFile.TrackFN}'.")
                                if not os.path.isfile(TrackPath + OrderedCueFile.TrackFN):
                                    raise RuntimeError(f"BIN Track '{TrackPath + OrderedCueFile.TrackFN}' is missing!")
                                with open(TrackPath + OrderedCueFile.TrackFN, "rb") as ImageTrack:
                                    MergedImage.write(ImageTrack.read())
                    TrackNum += 1
        print("Finished merging split track image!")

    def GetBinPath(self, FDRPath):
        # Get the name of the cue file without its extension
        BaseName = FDRPath[-1][:-4]

        # Check if the binary file exists with the exact path written in the cue
        if os.path.isfile(CUE.BinaryFN):
            CUE.BinPath = ""
        else:
            for i in range(len(FDRPath) - 1):  # Remove the CUE filename from the path
                CUE.BinPath += FDRPath[i] + os.sep

        # If still not found, search with BaseName
        if not os.path.isfile(CUE.BinPath + CUE.BinaryFN):
            if os.path.isfile(CUE.BinPath + BaseName + ".bin"):
                CUE.BinaryFN = BaseName + ".bin"
            elif os.path.isfile(CUE.BinPath + BaseName + ".img"):
                CUE.BinaryFN = BaseName + ".img"
            else:
                raise RuntimeError("Can't find the .BIN/.IMG image file anywhere!")
        return BaseName

    def ExportCue(self, ExportPath, BinaryPath):
        with open(ExportPath, "w") as ExportFile:
            if not ExportFile:
                raise RuntimeError(f"Error writing to '{ExportPath}'!")

            ExportFile.write(f'FILE "{BinaryPath}" BINARY\n')

            for CueFile in CUE.List:
                if CueFile.Index == 0:
                    ExportFile.write(f"  TRACK {CueFile.Track} {CueFile.TrackType}\n")
                elif CueFile.TrackType == "MODE2/2352":
                    ExportFile.write(f"  TRACK {CueFile.Track} MODE2/2352\n")
                    if CueFile.Sector > 150:
                        CueFile.Sector -= 150
                        CueFile.MSF = SectorToMSF(CueFile.Sector)
                ExportFile.write(f"    INDEX {CueFile.Index} {NumberToStrMSF(CueFile.MSF[0])}:{NumberToStrMSF(CueFile.MSF[1])}:{NumberToStrMSF(CueFile.MSF[2])}\n")
        print(f"Exported CUE to '{ExportPath}'.")

    def Clean(self):
        CUE.BinaryFN = ""
        CUE.BinPath = ""
        CUE.IsMultiTrack = False
        CUE.MultiSectorCount = 0
        CUE.List.clear()
        CUE.FDRPath = []


