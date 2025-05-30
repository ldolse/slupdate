import os
import shutil
from cd_utils import MSFToSector, SectorToMSF, GetSectorsBySize, NumberToStrMSF, crc16


class Cue:
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
        CUETrack = Cue()
        CUETrack.Track = Track
        CUETrack.TrackType = TrackType
        CUETrack.Index = Index
        CUETrack.TrackFN = FileName
        CUETrack.Sector = MSFToSector(Minutes, Seconds, Frames)

        # Alright, lets get the path of the CUE/Bin file(s)
        TrackPath = ""
        for x in range(len(Cue.FDRPath) - 2):  # Take 1 so it doesn't overflow, take another 1 to get rid of the CUE filename in this path
            TrackPath += Cue.FDRPath[x] + os.sep
            print(f'TrackPath is {TrackPath}')

        # handle multi track redump cue files
        if Cue.IsMultiTrack:
            # BIN file exists?
            if not os.path.isfile(TrackPath + FileName):
                raise RuntimeError(f"BIN Track '{TrackPath + FileName}' is missing!")
            if not os.path.isfile(TrackPath + Cue.BinaryFN):
                raise RuntimeError(f"BIN Track '{TrackPath + Cue.BinaryFN}' is missing!")  # Check for Track 1

            # Start counting!
            if Index == 0:
                CUETrack.Sector = Cue.MultiSectorCount
                print("Index 0, MultiSectorCount is: "+str(Cue.MultiSectorCount))
            elif Index == 1:
                CUETrack.Sector = Cue.MultiSectorCount + 150  # 2 Second LeadIn on Index 1's
                print("Index 1 pregap, MultiSectorCount is: "+str(Cue.MultiSectorCount))
                # Add the sector count of the next track
                Cue.MultiSectorCount += GetSectorsBySize(int(os.path.getsize(TrackPath + FileName)))
                print("Index 1, sectors from "+FileName+" MultiSectorCount is: "+str(Cue.MultiSectorCount))
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
            if os.path.isfile(TrackPath + Cue.BinaryFN):
                Cue.MultiSectorCount = GetSectorsBySize(int(os.path.getsize(TrackPath + Cue.BinaryFN)))
                print("Index 1, sectors from "+Cue.BinaryFN+" MultiSectorCount is: "+str(Cue.MultiSectorCount))
            else:
                print(f"Couldn't find {Cue.BinaryFN}")

        Cue.List.append(CUETrack)

    def AddCue(self, CuePath):
        """Parse and add tracks from a CUE file.
        
        Args:
            CuePath (str): Path to the CUE file.
        """
        # Open the file, fix the slashes
        CuePath = CuePath.replace("/", os.sep)
        # Set the path and read the CUE
        Cue.FDRPath = CuePath.split(os.sep)
        
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
                        if Cue.BinaryFN == "":
                            print(f'Processing the single track or first track in the cue class - line value: {line}')
                            Split = Line.split('"')  # Split the quotes
                            Cue.BinaryFN = Split[1]  # Set the filename the CUE links to in our global
                            print(f"Cue.BinaryFN is {Cue.BinaryFN}")
                            CurrentTrackFN = Split[1]  # Add it to the array afterwards
                        else:  # Oh ok so it's one of THOSE multi bin ones, nice. Lets fix it.
                            print(f'Processing the multi track mode in the cue class - Line: {Line}')
                            Split = Line.split('"')  # Split the quotes
                            CurrentTrackFN = Split[1]  # Add it to the array afterwards
                            # Oooh this is a separated track image!
                            if not Cue.IsMultiTrack:
                                Cue.IsMultiTrack = True
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
                            for IndexFixCue in Cue.List:
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
        if not Cue.FDRPath:
            raise RuntimeError("FDRPath is not populated.")
        
        print(f"Tracks found in CUE: {len(Cue.List)}")
        for track in Cue.List:
            print(f"Track: {track.Track}, Type: {track.TrackType}, Index: {track.Index}, Filename: {track.TrackFN}")

        print(f"FDRPath: {'/'.join(Cue.FDRPath)}")


    def CountCDDA(self, CountData=False):
        """Counts all the tracks, excluding the data tracks by default"""
        TrackCount = 0
        for CueFile in Cue.List:
            if CueFile.Index == 0:
                TrackCount += 1
            elif CountData:
                if CueFile.Index == 1 and CueFile.TrackType == "MODE2/2352":
                    TrackCount += 1
        return TrackCount

    def MergeImage(self, ExportPath):
        with open(ExportPath, "wb") as MergedImage:
            TrackNum = 1
            for CueFile in Cue.List:
                if CueFile.Index == 1:
                    # Get the path of the bin file(s)
                    TrackPath = ""
                    for x in range(len(Cue.FDRPath) - 2):  # Take 1 so it doesn't overflow, take another to remove the CUE filename in this path
                        TrackPath += Cue.FDRPath[x] + os.sep

                    # Verification to check the track numbers are correct
                    if CueFile.Track == TrackNum:
                        print(f"Stitching '{CueFile.TrackFN}'.")
                        if not os.path.isfile(TrackPath + CueFile.TrackFN):
                            raise RuntimeError(f"BIN Track '{TrackPath + CueFile.TrackFN}' is missing!")
                        with open(TrackPath + CueFile.TrackFN, "rb") as ImageTrack:
                            MergedImage.write(ImageTrack.read())
                    else:
                        for OrderedCueFile in Cue.List:
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
        if os.path.isfile(Cue.BinaryFN):
            Cue.BinPath = ""
        else:
            for i in range(len(FDRPath) - 1):  # Remove the CUE filename from the path
                Cue.BinPath += FDRPath[i] + os.sep

        # If still not found, search with BaseName
        if not os.path.isfile(Cue.BinPath + Cue.BinaryFN):
            if os.path.isfile(Cue.BinPath + BaseName + ".bin"):
                Cue.BinaryFN = BaseName + ".bin"
            elif os.path.isfile(Cue.BinPath + BaseName + ".img"):
                Cue.BinaryFN = BaseName + ".img"
            else:
                raise RuntimeError("Can't find the .BIN/.IMG image file anywhere!")
        return BaseName

    def ExportCue(self, ExportPath, BinaryPath):
        with open(ExportPath, "w") as ExportFile:
            if not ExportFile:
                raise RuntimeError(f"Error writing to '{ExportPath}'!")

            ExportFile.write(f'FILE "{BinaryPath}" BINARY\n')

            for CueFile in Cue.List:
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
        Cue.BinaryFN = ""
        Cue.BinPath = ""
        Cue.IsMultiTrack = False
        Cue.MultiSectorCount = 0
        Cue.List.clear()
        Cue.FDRPath = []

def export_cue(cue: Cue):
    base_name = cue.GetBinPath(cue.FDRPath)
    print("Creating modified CUE")
    cue_path = os.path.join("CCD", base_name, f"{base_name}.cue")
    img_file = f"{base_name}.img"
    cue.ExportCue(cue_path, img_file)
    print("Done writing CUE!")

def ccd_Generator(cue: Cue):
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
    

def handle_image(cue: Cue):
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
