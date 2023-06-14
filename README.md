# slupdate
MAME CD Media CHD Builder / Software List Updater
 
## Introduction
slupdate parses MAME CD Media Software Lists to find source ROM information, and then maps those source references to externally managed DAT and ROM files. In the event that source information in the Software List can be matched to a DAT entry, it will then check to see if ROM files exist for that DAT entry. Valid matches can then be converted to CHDs, and if the Software List CHD hash is out of date it can update the Software List.

## Prerequisites
* You should have DAT files from groups such as Redump or TOSEC, and ROM directories which have already been updated to match the DAT using tools such as RomVault, RomCenter, or clrmamepro.
* DAT files should be stored in separate folders for each platform (or individual DAT), multiple platform DATs in a single directory are not supported.
* ROM files should be stored compressed in zip format, other types of filetype storage options may be added later based on demand.

## Installation
Download the source and unzip into a folder, ensure Python 3.x and chdman are in the path, or optionally place a chdman binary in the slupdate directory if you don't want it in the system path.

Ensure the required Python modules (see below) are installed using pip or your preferred Python package manager.

#### Required Python Modules

xmltodict, inquirer, lxml


## Using the Software
### Typical Usage
* Ensure a set of DATs for your target console/platform are configured under settings
* Select 'Mapping Functions' and choose a platform. slupdate will parse the software list for DAT and ROM matches, valid source ROM matches will then be displayed
* If desired build CHDs and update the Softlist with any changed hashes

### First Run
On first run you'll be automatically directed to configure mandatory settings:
1. The location of the MAME 'hash' directory containing the Software List XML files
2. The root directories for you DAT and ROM files, if you are a ROMVault user this should be the DatRoot and RomRoot configured in Romvault.  
   * If you are not a Romvault user these settings are still used as a starting point for selecting DAT & ROM directories for specific platforms.
3. Configure whether or not RomVault is used as the DAT/ROM Manager - RomVault users need only specify source DAT files, ROM directories are calculated based on DatRoot and RomRoot.
4. Configure first platform specific DAT & ROM directory.
    * You'll be asked to select a Software List platform, and then select a directory containing DATs for that platform
		- If you're using ROMVault, and RomVault has already created ROM directories for the DATs then this step is complete
    * Otherwise you'll be queried for a ROM directory corresponding to each DAT found
    * Go to Settings after this initial configuration to add more DAT directories for this platform or others
5. Configure CHD Destination Directory
	* Follow the prompts to set the CHD Destination, this shouldn't be a directory that includes MAME CHDs from other sources, as this script will not overwrite existing CHDs.
    * Configure a directory for temporary files - if you are using an SSD hard disk you may want to choose a magnetic media or tmpfs/ramdisk destination to avoid thrashing your SSD

## Known Limitations
* These are the known limitations, please file a bug if there are other issues that should be flagged and/or appropriately handled
* Many Software Lists contain no direct source references, the following softlists include data which can be parsed:
  - Philips CDi
  - Amiga CDTV
  - Dreamcast
  - PSX
  - SegaCD/MegaCD
* Only Software Lists which contain source ROM information in source comments that are nested 'inside' the software list entry are parsed at this point
* clonecd is not supported
* multi-disk sets using different types of dumps may not be parsed
* Redump sources for Philips CDI are not yet supported
* This does not yet monitor the Chdman output for warnings which would indicate an invalid CHD, this will be added later.  Please use caution and review the logs for warnings.



