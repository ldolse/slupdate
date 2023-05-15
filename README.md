### slupdate
 Software List Updater
 
## Introduction
slupdate parses Software Lists to find source ROM information, and then maps those source references to externally managed DAT and ROM files. In the event that source information in the Software List can be matched to a DAT entry, it will then check to see if ROM files exist for that DAT entry. Valid matches can then be converted to CHDs, and if the Software List CHD hash is out of date it can update the Software List.

## Prerequisites
* You should have DAT files from groups such as Redump or TOSEC, and ROM directories which have already been updated to match the DAT using tools like RomVault, RomCenter, or clrmamepro.
* DAT files should be stored in separate folders for each you want to use this script with.
* ROM files should be stored compressed in zip format, other types of filetype storage options may be added later based on demand.

## Installation
Download the source and unzip into a folder, ensure Python 3.x and chdman are in the path, or optionally place a chdman binary in the slupdate directory if you don't want it in the system path.

Ensure the required Python modules are installed using pip or your preferred Python package manager.

## Using the Software
# Typical Usage
* Ensure a set of DATs for your target platform is configured under settings
* 
# First Run
On first run you'll be automatically directed to the settings, the following are required to get started:
 1. The location of the MAME 'hash' directory containing the Software List XML files
2. The root directories for you DAT and ROM files, if you are a ROMVault user this should be the DatRoot and RomRoot used by Romvault.  
 If you are not a Romvault user this preference is still used as a starting point for selecting DAT & ROM directories for specific platforms.
  3. Configure whether or not RomVault is used as the DAT/ROM Manager - RomVault users need only specify source DAT files, ROM directories are calculated based on DatRoot and RomRoot.
 4. Configure DAT & ROM Directories - Configure at least one Platform
    * You'll be asked to select a Software List platform, and then select a directory containing DATs for that platform
		- If you're using ROMVault, and RomVault has already created ROM directories for the DATs then this step is complete
    * Otherwise you'll be queried for a ROM directory corresponding to each DAT found
    * Add other DAT directories on per platform basis as needed
 5. Configure CHD Destination Directory
	* Follow the prompts to set the CHD Destination, this shouldn't be a directory that includes MAME CHDs from other sources, as this script will not overwrite existing CHDs.
    - Configure a directory for temporary files - if you are using an SSD hard disk you may want to choose a magnetic media or tmpfs/ramdisk destination to avoid thrashing your SSD
 
## Known Limitations
* These are the known limitations, please file a bug if there are other issues that should be flagged and/or appropriately handled
* Only Software Lists which contain source ROM information in source comments that are nested 'inside' the software list entry are supported.  Some Software Lists contain no source references, other software lists may have the source information 'outside' the Software Entry's tag
* Only ROMs using cue and gdi TOC files are supported at this time
* Philips CDI is not yet supported
* This does not yet monitor the Chdman output for warnings which would indicate an invalid CHD, this will be added later.
    
## Required Pythont Modules
# To build CHDs
xmltodict, inquirer,

# Future functions
 requests, beautifulsoup4, pykakasi


