import struct
from .constants import *
from .structs import CdrdaoTrack
from modules.CD.cd_types import TrackType, Track
from modules.CD.fulltoc import FullTOC, TrackDataDescriptor, CDFullTOC

@staticmethod
def cdrdao_track_type_to_cooked_bytes_per_sector(track_type: str) -> int:
	if track_type in [Cdrdao.CDRDAO_TRACK_TYPE_MODE1, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM1, Cdrdao.CDRDAO_TRACK_TYPE_MODE1_RAW]:
		return 2048
	elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM2:
		return 2324
	elif track_type in [Cdrdao.CDRDAO_TRACK_TYPE_MODE2, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_MIX, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_RAW]:
		return 2336
	elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_AUDIO:
		return 2352
	else:
		return 0

@staticmethod
def cdrdao_track_type_to_track_type(track_type: str) -> TrackType:
	if track_type in [Cdrdao.CDRDAO_TRACK_TYPE_MODE1, Cdrdao.CDRDAO_TRACK_TYPE_MODE1_RAW]:
		return TrackType.CdMode1
	elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM1:
		return TrackType.CdMode2Form1
	elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM2:
		return TrackType.CdMode2Form2
	elif track_type in [Cdrdao.CDRDAO_TRACK_TYPE_MODE2, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_MIX, Cdrdao.CDRDAO_TRACK_TYPE_MODE2_RAW]:
		return TrackType.CdMode2Formless
	elif track_type == Cdrdao.CDRDAO_TRACK_TYPE_AUDIO:
		return TrackType.Audio
	else:
		return TrackType.Data

@staticmethod
def lba_to_msf(sector: int) -> Tuple[int, int, int]:
	return (sector // 75 // 60, (sector // 75) % 60, sector % 75)

@staticmethod
def get_track_mode(track: 'Track') -> str:
	if track.type == TrackType.Audio and track.raw_bytes_per_sector == 2352:
		return Cdrdao.CDRDAO_TRACK_TYPE_AUDIO
	elif track.type == TrackType.Data:
		return Cdrdao.CDRDAO_TRACK_TYPE_MODE1
	elif track.type == TrackType.CdMode1 and track.raw_bytes_per_sector == 2352:
		return Cdrdao.CDRDAO_TRACK_TYPE_MODE1_RAW
	elif track.type == TrackType.CdMode2Formless and track.raw_bytes_per_sector != 2352:
		return Cdrdao.CDRDAO_TRACK_TYPE_MODE2
	elif track.type == TrackType.CdMode2Form1 and track.raw_bytes_per_sector != 2352:
		return Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM1
	elif track.type == TrackType.CdMode2Form2 and track.raw_bytes_per_sector != 2352:
		return Cdrdao.CDRDAO_TRACK_TYPE_MODE2_FORM2
	elif track.type in [TrackType.CdMode2Formless, TrackType.CdMode2Form1, TrackType.CdMode2Form2] and track.raw_bytes_per_sector == 2352:
		return Cdrdao.CDRDAO_TRACK_TYPE_MODE2_RAW
	else:
		return Cdrdao.CDRDAO_TRACK_TYPE_MODE1

def _swap_audio_endianness(self, buffer: bytearray) -> bytearray:
	return bytearray(buffer[i+1] + buffer[i] for i in range(0, len(buffer), 2))

def _get_sector_layout(self, track: 'CdrdaoTrack') -> Tuple[int, int, int, bool]:
	sector_offset = 0
	sector_size = self.cdrdao_track_type_to_cooked_bytes_per_sector(track.tracktype)
	sector_skip = 0
	mode2 = False

	if track.tracktype in [self.CDRDAO_TRACK_TYPE_MODE1, self.CDRDAO_TRACK_TYPE_MODE2_FORM1]:
		sector_offset = 0
		sector_skip = 0
	elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_FORM2:
		sector_offset = 0
		sector_skip = 0
	elif track.tracktype in [self.CDRDAO_TRACK_TYPE_MODE2, self.CDRDAO_TRACK_TYPE_MODE2_MIX]:
		mode2 = True
		sector_offset = 0
		sector_skip = 0
	elif track.tracktype == self.CDRDAO_TRACK_TYPE_AUDIO:
		sector_offset = 0
		sector_skip = 0
	elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE1_RAW:
		sector_offset = 16
		sector_skip = 288
	elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_RAW:
		mode2 = True
		sector_offset = 0
		sector_skip = 0
	else:
		raise ValueError(f"Unsupported track type: {track.tracktype}")

	if track.subchannel:
		sector_skip += 96

	return sector_offset, sector_size, sector_skip, mode2

def _get_tag_layout(self, track: CdrdaoTrack, tag: SectorTagType) -> Tuple[int, int, int]:
	sector_offset = 0
	sector_size = 0
	sector_skip = 0

	if track.tracktype == self.CDRDAO_TRACK_TYPE_MODE1:
		if tag == SectorTagType.CdSectorSync:
			sector_offset, sector_size, sector_skip = 0, 12, 2340
		elif tag == SectorTagType.CdSectorHeader:
			sector_offset, sector_size, sector_skip = 12, 4, 2336
		elif tag == SectorTagType.CdSectorSubHeader:
			raise ValueError("Unsupported tag type for Mode 1")
		elif tag == SectorTagType.CdSectorEcc:
			sector_offset, sector_size, sector_skip = 2076, 276, 0
		elif tag == SectorTagType.CdSectorEccP:
			sector_offset, sector_size, sector_skip = 2076, 172, 104
		elif tag == SectorTagType.CdSectorEccQ:
			sector_offset, sector_size, sector_skip = 2248, 104, 0
		elif tag == SectorTagType.CdSectorEdc:
			sector_offset, sector_size, sector_skip = 2064, 4, 284
		else:
			raise ValueError("Unsupported tag type for Mode 1")
	elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_FORMLESS:
		if tag in [SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader, 
				   SectorTagType.CdSectorEcc, SectorTagType.CdSectorEccP, SectorTagType.CdSectorEccQ]:
			raise ValueError("Unsupported tag type for Mode 2 Formless")
		elif tag == SectorTagType.CdSectorSubHeader:
			sector_offset, sector_size, sector_skip = 0, 8, 2328
		elif tag == SectorTagType.CdSectorEdc:
			sector_offset, sector_size, sector_skip = 2332, 4, 0
		else:
			raise ValueError("Unsupported tag type for Mode 2 Formless")
	elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_FORM1:
		if tag == SectorTagType.CdSectorSync:
			sector_offset, sector_size, sector_skip = 0, 12, 2340
		elif tag == SectorTagType.CdSectorHeader:
			sector_offset, sector_size, sector_skip = 12, 4, 2336
		elif tag == SectorTagType.CdSectorSubHeader:
			sector_offset, sector_size, sector_skip = 16, 8, 2328
		elif tag == SectorTagType.CdSectorEcc:
			sector_offset, sector_size, sector_skip = 2076, 276, 0
		elif tag == SectorTagType.CdSectorEccP:
			sector_offset, sector_size, sector_skip = 2076, 172, 104
		elif tag == SectorTagType.CdSectorEccQ:
			sector_offset, sector_size, sector_skip = 2248, 104, 0
		elif tag == SectorTagType.CdSectorEdc:
			sector_offset, sector_size, sector_skip = 2072, 4, 276
		else:
			raise ValueError("Unsupported tag type for Mode 2 Form 1")
	elif track.tracktype == self.CDRDAO_TRACK_TYPE_MODE2_FORM2:
		if tag == SectorTagType.CdSectorSync:
			sector_offset, sector_size, sector_skip = 0, 12, 2340
		elif tag == SectorTagType.CdSectorHeader:
			sector_offset, sector_size, sector_skip = 12, 4, 2336
		elif tag == SectorTagType.CdSectorSubHeader:
			sector_offset, sector_size, sector_skip = 16, 8, 2328
		elif tag == SectorTagType.CdSectorEdc:
			sector_offset, sector_size, sector_skip = 2348, 4, 0
		else:
			raise ValueError("Unsupported tag type for Mode 2 Form 2")

	if sector_size == 0:
		raise ValueError(f"Unsupported tag type {tag} for track type {track.tracktype}")

	return sector_offset, sector_size, sector_skip

def _create_full_toc(self) -> None:
	toc = CDFullTOC()
	session_ending_track = {}
	toc.first_complete_session = 255
	toc.last_complete_session = 0
	track_descriptors = []
	current_track = 0

	for track in sorted(self._discimage.tracks, key=lambda t: t.sequence):
		if track.sequence < toc.first_complete_session:
			toc.first_complete_session = track.sequence

		if track.sequence <= toc.last_complete_session:
			current_track = track.sequence
			continue

		if toc.last_complete_session > 0:
			session_ending_track[toc.last_complete_session] = current_track

		toc.last_complete_session = track.sequence

	session_ending_track[toc.last_complete_session] = max(t.sequence for t in self._discimage.tracks)

	current_session = 0

	for track in sorted(self._discimage.tracks, key=lambda t: t.sequence):
		track_control = self._track_flags.get(track.sequence, 0)

		if track_control == 0 and track.tracktype != self.CDRDAO_TRACK_TYPE_AUDIO:
			track_control = 0x04  # Data track flag

		# Lead-Out
		if track.sequence > current_session and current_session != 0:
			leadout_amsf = self.lba_to_msf(track.start_sector - 150) # subtract 150 for lead-in
			leadout_pmsf = self.lba_to_msf(max(t.start_sector for t in self._discimage.tracks))

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

			leadin_pmsf = self.lba_to_msf(next((t.start_sector + t.sectors for t in self._discimage.tracks if t.sequence == ending_track_number), 0))

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

		pmsf = self.lba_to_msf(track.indexes.get(1, track.start_sector))

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

	self._full_toc = toc_ms.getvalue()

def _determine_media_type(self):
	data_tracks = sum(1 for track in self._discimage.tracks if track.tracktype != self.CDRDAO_TRACK_TYPE_AUDIO)
	audio_tracks = len(self._discimage.tracks) - data_tracks
	mode2_tracks = sum(1 for track in self._discimage.tracks if track.tracktype in [
		self.CDRDAO_TRACK_TYPE_MODE2, self.CDRDAO_TRACK_TYPE_MODE2_FORM1, 
		self.CDRDAO_TRACK_TYPE_MODE2_FORM2, self.CDRDAO_TRACK_TYPE_MODE2_MIX, 
		self.CDRDAO_TRACK_TYPE_MODE2_RAW
	])
	
	if data_tracks == 0:
		return MediaType.CDDA
	elif self._discimage.tracks[0].tracktype == self.CDRDAO_TRACK_TYPE_AUDIO and data_tracks > 0 and len(self.sessions) > 1 and mode2_tracks > 0:
		return MediaType.CDPLUS
	elif (self._discimage.tracks[0].tracktype != self.CDRDAO_TRACK_TYPE_AUDIO and audio_tracks > 0) or mode2_tracks > 0:
		return MediaType.CDROMXA
	elif audio_tracks == 0:
		return MediaType.CDROM
	else:
		return MediaType.CD

def _parse_cd_text(self, cd_text_data: bytes) -> None:
	if not cd_text_data:
		return

	pack_type = 0
	track_number = 0
	block_number = 0
	text_buffer = bytearray()

	for i in range(0, len(cd_text_data), 18):
		pack = cd_text_data[i:i+18]
		pack_type = pack[0] & 0x0F
		track_number = pack[1]
		block_number = pack[2]
		text = pack[4:16]

		if pack_type == 0x80:
			text_buffer.extend(text)
			if pack[3] & 0x80:
				self._process_cd_text(pack_type, track_number, text_buffer.decode('ascii', errors='ignore'))
				text_buffer.clear()
		else:
			self._process_cd_text(pack_type, track_number, text.decode('ascii', errors='ignore'))

def _process_cd_text(self, pack_type: int, track_number: int, text: str) -> None:
	if track_number == 0:
		self._process_disc_cd_text(pack_type, text)
	else:
		self._process_track_cd_text(pack_type, track_number, text)

def _process_disc_cd_text(self, pack_type: int, text: str) -> None:
	if pack_type == 0x80:
		self._discimage.title = text
	elif pack_type == 0x81:
		self._discimage.performer = text
	elif pack_type == 0x82:
		self._discimage.songwriter = text
	elif pack_type == 0x83:
		self._discimage.composer = text
	elif pack_type == 0x84:
		self._discimage.arranger = text
	elif pack_type == 0x85:
		self._discimage.message = text
	elif pack_type == 0x86:
		self._discimage.disk_id = text
	elif pack_type == 0x87:
		self._discimage.genre = text
	elif pack_type == 0x8E:
		self._discimage.barcode = text

def _process_track_cd_text(self, pack_type: int, track_number: int, text: str) -> None:
	track = next((t for t in self._discimage.tracks if t.sequence == track_number), None)
	if track:
		if pack_type == 0x80:
			track.title = text
		elif pack_type == 0x81:
			track.performer = text
		elif pack_type == 0x82:
			track.songwriter = text
		elif pack_type == 0x83:
			track.composer = text
		elif pack_type == 0x84:
			track.arranger = text
		elif pack_type == 0x85:
			track.message = text
		elif pack_type == 0x86:
			track.isrc = text
		elif pack_type == 0x87:
			track.genre = text
