"""AudioScope Exhaustive Metadata & Broadcast Tag Parsing Engine.

Extracts standard tags via mutagen, and natively parses broadcast chunks:
Broadcast Wave (bext), iXML production metadata, CART (AES46-2002),
and embedded artwork.
"""

from __future__ import annotations

import io
import os
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import mutagen
from PIL import Image


@dataclass
class BextMetadata:
    """Broadcast Wave (bext) chunk metadata per EBU Tech 3285."""
    description: str = ""
    originator: str = ""
    originator_reference: str = ""
    origination_date: str = ""
    origination_time: str = ""
    time_reference: int = 0  # Samples since midnight
    timecode_start: str = "00:00:00:00"
    version: int = 0
    umid: str = ""
    loudness_value_lufs: Optional[float] = None
    loudness_range_lu: Optional[float] = None
    max_true_peak_dbtp: Optional[float] = None
    max_momentary_lufs: Optional[float] = None
    max_short_term_lufs: Optional[float] = None
    coding_history: str = ""


@dataclass
class IXMLElementTrack:
    """iXML track description."""
    channel_index: str = ""
    interleave_index: str = ""
    name: str = ""
    function: str = ""


@dataclass
class IXMLMetadata:
    """iXML production audio metadata."""
    project: str = ""
    scene: str = ""
    take: str = ""
    tape: str = ""
    circled: bool = False
    notes: str = ""
    timecode_rate: str = ""
    timecode_flag: str = ""
    file_sample_rate: str = ""
    audio_bit_depth: str = ""
    sync_point_sample: str = ""
    family_uid: str = ""
    tracks: List[IXMLElementTrack] = field(default_factory=list)
    raw_xml: str = ""


@dataclass
class CartMetadata:
    """AES46-2002 CART chunk radio automation metadata."""
    version: str = ""
    title: str = ""
    artist: str = ""
    cut_id: str = ""
    client_id: str = ""
    category: str = ""
    classification: str = ""
    out_cue: str = ""
    start_date: str = ""
    start_time: str = ""
    end_date: str = ""
    end_time: str = ""
    producer_app_id: str = ""
    producer_app_version: str = ""
    user_def: str = ""
    level_reference: int = 0
    url: str = ""


@dataclass
class EmbeddedArtwork:
    """Embedded album artwork details."""
    mime_type: str = "image/jpeg"
    width: int = 0
    height: int = 0
    byte_size: int = 0
    picture_type: str = "Front Cover"
    description: str = ""
    raw_data: bytes = field(default=b"", repr=False)

    @property
    def dimensions_str(self) -> str:
        if self.width > 0 and self.height > 0:
            return f"{self.width} × {self.height}"
        return "Unknown dimensions"

    @property
    def formatted_size(self) -> str:
        kb = self.byte_size / 1024.0
        if kb < 1024:
            return f"{kb:.1f} KB"
        return f"{kb / 1024.0:.2f} MB"


@dataclass
class FileMetadata:
    """Unified container for all extracted metadata."""
    # Normalized standard tags
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    date: str = ""
    genre: str = ""
    track_number: str = ""
    disc_number: str = ""
    composer: str = ""
    publisher: str = ""
    isrc: str = ""
    bpm: str = ""
    copyright: str = ""
    comment: str = ""
    encoder: str = ""

    # Broadcast specific chunks
    bext: Optional[BextMetadata] = None
    ixml: Optional[IXMLMetadata] = None
    cart: Optional[CartMetadata] = None

    # Embedded artwork
    artwork: Optional[EmbeddedArtwork] = None

    # All unmapped tags dictionary
    raw_tags: Dict[str, str] = field(default_factory=dict)


class MetadataEngine:
    """Unified metadata extractor with broadcast chunk decoders."""

    @staticmethod
    def extract(file_path: str, sample_rate: int = 48000) -> FileMetadata:
        """Exhaustively parse all metadata, broadcast chunks, and embedded artwork."""
        result = FileMetadata()

        # 1. Native Binary Chunk Extraction (BEXT, iXML, CART) from RIFF/AIFF or raw file
        try:
            MetadataEngine._parse_binary_chunks(file_path, result, sample_rate)
        except Exception:
            pass

        # 2. Mutagen extraction for standard tags & artwork
        try:
            m_file = mutagen.File(file_path)
            if m_file is not None:
                MetadataEngine._extract_mutagen_tags(m_file, result)
        except Exception:
            pass

        return result

    @staticmethod
    def _parse_binary_chunks(file_path: str, result: FileMetadata, sample_rate: int) -> None:
        """Scan file for RIFF/AIFF chunks including 'bext', 'iXML', 'cart'."""
        if not os.path.isfile(file_path):
            return

        with open(file_path, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                return

            riff_id = header[:4]
            if riff_id in (b"RIFF", b"RIFX", b"RF64"):
                # RIFF WAVE container
                is_be = (riff_id == b"RIFX")
                endian = ">" if is_be else "<"
                f.seek(12)

                while True:
                    chunk_hdr = f.read(8)
                    if len(chunk_hdr) < 8:
                        break

                    chunk_id = chunk_hdr[:4]
                    chunk_size = struct.unpack(f"{endian}I", chunk_hdr[4:8])[0]
                    chunk_data_pos = f.tell()

                    if chunk_id == b"bext":
                        bext_bytes = f.read(chunk_size)
                        result.bext = MetadataEngine.parse_bext_chunk(bext_bytes, sample_rate)
                    elif chunk_id in (b"iXML", b"ixml"):
                        ixml_bytes = f.read(chunk_size)
                        result.ixml = MetadataEngine.parse_ixml_chunk(ixml_bytes)
                    elif chunk_id == b"cart":
                        cart_bytes = f.read(chunk_size)
                        result.cart = MetadataEngine.parse_cart_chunk(cart_bytes)
                    else:
                        f.seek(chunk_data_pos + chunk_size)

                    # RIFF chunks are 2-byte word aligned
                    if chunk_size % 2 != 0:
                        f.seek(1, io.SEEK_CUR)

            elif riff_id == b"FORM":
                # AIFF container
                f.seek(12)
                while True:
                    chunk_hdr = f.read(8)
                    if len(chunk_hdr) < 8:
                        break
                    chunk_id = chunk_hdr[:4]
                    chunk_size = struct.unpack(">I", chunk_hdr[4:8])[0]
                    chunk_data_pos = f.tell()

                    if chunk_id == b"bext":
                        bext_bytes = f.read(chunk_size)
                        result.bext = MetadataEngine.parse_bext_chunk(bext_bytes, sample_rate)
                    elif chunk_id in (b"iXML", b"ixml"):
                        ixml_bytes = f.read(chunk_size)
                        result.ixml = MetadataEngine.parse_ixml_chunk(ixml_bytes)
                    else:
                        f.seek(chunk_data_pos + chunk_size)

                    if chunk_size % 2 != 0:
                        f.seek(1, io.SEEK_CUR)

    @staticmethod
    def parse_bext_chunk(data: bytes, sample_rate: int = 48000) -> Optional[BextMetadata]:
        """Parse binary BEXT chunk per EBU Tech 3285."""
        if len(data) < 256 + 32 + 32 + 10 + 8 + 8 + 2:
            return None

        # BEXT layout:
        # 0:256 - Description (256 ASCII)
        # 256:288 - Originator (32 ASCII)
        # 288:320 - OriginatorReference (32 ASCII)
        # 320:330 - OriginationDate (10 ASCII)
        # 330:338 - OriginationTime (8 ASCII)
        # 338:346 - TimeReference (uint64 LE: low 32 + high 32)
        # 346:348 - Version (uint16 LE)
        # 348:412 - UMID (64 bytes)
        # 412:414 - LoudnessValue (int16 LE, s16 / 100 = LUFS)
        # 414:416 - LoudnessRange (int16 LE, s16 / 100 = LU)
        # 416:418 - MaxTruePeakLevel (int16 LE, s16 / 100 = dBTP)
        # 418:420 - MaxMomentaryLoudness (int16 LE, s16 / 100 = LUFS)
        # 420:422 - MaxShortTermLoudness (int16 LE, s16 / 100 = LUFS)
        # 422:602 - Reserved (180 bytes)
        # 602: - CodingHistory (ASCII)

        def clean_str(b: bytes) -> str:
            return b.split(b"\x00")[0].decode("ascii", errors="replace").strip()

        desc = clean_str(data[0:256])
        orig = clean_str(data[256:288])
        orig_ref = clean_str(data[288:320])
        orig_date = clean_str(data[320:330])
        orig_time = clean_str(data[330:338])

        time_ref_low, time_ref_high = struct.unpack("<II", data[338:346])
        time_ref = (time_ref_high << 32) | time_ref_low

        version = struct.unpack("<H", data[346:348])[0]

        # Calculate timecode from sample count since midnight
        timecode_str = "00:00:00:00"
        if sample_rate > 0 and time_ref > 0:
            total_sec = time_ref / float(sample_rate)
            hh = int(total_sec // 3600) % 24
            mm = int((total_sec % 3600) // 60)
            ss = int(total_sec % 60)
            rem_sec = total_sec - int(total_sec)
            ff = int(round(rem_sec * 24.0))  # Default 24fps reference
            timecode_str = f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

        umid_hex = data[348:412].hex() if len(data) >= 412 else ""

        lufs_val = None
        lra_val = None
        tp_val = None
        mom_val = None
        st_val = None

        if len(data) >= 422 and version >= 1:
            lv, lr, tp, ml, sl = struct.unpack("<hhhhh", data[412:422])
            if lv != 0x7FFF and lv != -0x8000:
                lufs_val = round(lv / 100.0, 2)
            if lr != 0x7FFF and lr != -0x8000:
                lra_val = round(lr / 100.0, 2)
            if tp != 0x7FFF and tp != -0x8000:
                tp_val = round(tp / 100.0, 2)
            if ml != 0x7FFF and ml != -0x8000:
                mom_val = round(ml / 100.0, 2)
            if sl != 0x7FFF and sl != -0x8000:
                st_val = round(sl / 100.0, 2)

        coding_history = ""
        if len(data) > 602:
            coding_history = data[602:].split(b"\x00")[0].decode("latin-1", errors="replace").strip()

        return BextMetadata(
            description=desc,
            originator=orig,
            originator_reference=orig_ref,
            origination_date=orig_date,
            origination_time=orig_time,
            time_reference=time_ref,
            timecode_start=timecode_str,
            version=version,
            umid=umid_hex,
            loudness_value_lufs=lufs_val,
            loudness_range_lu=lra_val,
            max_true_peak_dbtp=tp_val,
            max_momentary_lufs=mom_val,
            max_short_term_lufs=st_val,
            coding_history=coding_history,
        )

    @staticmethod
    def parse_ixml_chunk(data: bytes) -> Optional[IXMLMetadata]:
        """Parse iXML XML chunk."""
        # Strip trailing nulls
        clean_xml = data.rstrip(b"\x00").decode("utf-8", errors="replace").strip()
        if not clean_xml:
            return None

        try:
            root = ET.fromstring(clean_xml)
        except Exception:
            return IXMLMetadata(raw_xml=clean_xml)

        def find_text(elem: Optional[ET.Element], path: str) -> str:
            if elem is None:
                return ""
            sub = elem.find(path)
            return (sub.text or "").strip() if sub is not None else ""

        tracks: List[IXMLElementTrack] = []
        track_list_elem = root.find("TRACK_LIST")
        if track_list_elem is not None:
            for trk in track_list_elem.findall("TRACK"):
                tracks.append(
                    IXMLElementTrack(
                        channel_index=find_text(trk, "CHANNEL_INDEX"),
                        interleave_index=find_text(trk, "INTERLEAVE_INDEX"),
                        name=find_text(trk, "NAME"),
                        function=find_text(trk, "FUNCTION"),
                    )
                )

        speed_elem = root.find("SPEED")

        circled_str = find_text(root, "CIRCLED").upper()
        is_circled = circled_str in ("TRUE", "1", "YES")

        return IXMLMetadata(
            project=find_text(root, "PROJECT"),
            scene=find_text(root, "SCENE"),
            take=find_text(root, "TAKE"),
            tape=find_text(root, "TAPE"),
            circled=is_circled,
            notes=find_text(root, "NOTE") or find_text(root, "NOTES"),
            timecode_rate=find_text(speed_elem, "TIMECODE_RATE"),
            timecode_flag=find_text(speed_elem, "TIMECODE_FLAG"),
            file_sample_rate=find_text(speed_elem, "FILE_SAMPLE_RATE"),
            audio_bit_depth=find_text(speed_elem, "AUDIO_BIT_DEPTH"),
            sync_point_sample=find_text(root, "SYNC_POINT_LIST/SYNC_POINT/SYNC_POINT_LOW"),
            family_uid=find_text(root, "FAMILY_UID"),
            tracks=tracks,
            raw_xml=clean_xml,
        )

    @staticmethod
    def parse_cart_chunk(data: bytes) -> Optional[CartMetadata]:
        """Parse AES46-2002 CART chunk."""
        if len(data) < 4 + 64 + 64 + 64:
            return None

        def clean_str(b: bytes) -> str:
            return b.split(b"\x00")[0].decode("ascii", errors="replace").strip()

        version = clean_str(data[0:4])
        title = clean_str(data[4:68])
        artist = clean_str(data[68:132])
        cut_id = clean_str(data[132:196])
        client_id = clean_str(data[196:260]) if len(data) >= 260 else ""
        category = clean_str(data[260:324]) if len(data) >= 324 else ""
        classification = clean_str(data[324:388]) if len(data) >= 388 else ""
        out_cue = clean_str(data[388:452]) if len(data) >= 452 else ""
        start_date = clean_str(data[452:462]) if len(data) >= 462 else ""
        start_time = clean_str(data[462:470]) if len(data) >= 470 else ""
        end_date = clean_str(data[470:480]) if len(data) >= 480 else ""
        end_time = clean_str(data[480:488]) if len(data) >= 488 else ""
        producer_app_id = clean_str(data[488:552]) if len(data) >= 552 else ""
        producer_app_version = clean_str(data[552:616]) if len(data) >= 616 else ""
        user_def = clean_str(data[616:680]) if len(data) >= 680 else ""

        url = ""
        if len(data) > 680:
            url = clean_str(data[680:1704])

        return CartMetadata(
            version=version,
            title=title,
            artist=artist,
            cut_id=cut_id,
            client_id=client_id,
            category=category,
            classification=classification,
            out_cue=out_cue,
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
            producer_app_id=producer_app_id,
            producer_app_version=producer_app_version,
            user_def=user_def,
            url=url,
        )

    @staticmethod
    def _extract_mutagen_tags(m_file: mutagen.FileType, result: FileMetadata) -> None:
        """Extract tags and embedded artwork from mutagen File object."""
        if not hasattr(m_file, "tags") or m_file.tags is None:
            return

        tags = m_file.tags

        # Populate raw tags dictionary
        for k in tags.keys():
            try:
                v = tags[k]
                if isinstance(v, list):
                    result.raw_tags[str(k)] = ", ".join(str(item) for item in v)
                else:
                    result.raw_tags[str(k)] = str(v)
            except Exception:
                pass

        # Helper to retrieve first matching tag from a list of aliases
        def get_tag(*keys: str) -> str:
            for key in keys:
                # Direct match
                if key in tags:
                    val = tags[key]
                    if isinstance(val, list) and val:
                        return str(val[0]).strip()
                    return str(val).strip()
                # Case-insensitive match
                for tk in tags.keys():
                    if tk.lower() == key.lower():
                        val = tags[tk]
                        if isinstance(val, list) and val:
                            return str(val[0]).strip()
                        return str(val).strip()
            return ""

        # Map standard tags
        if not result.title:
            result.title = get_tag("TIT2", "title", "\xa9nam", "TITLE")
        if not result.artist:
            result.artist = get_tag("TPE1", "artist", "\xa9ART", "ARTIST")
        if not result.album:
            result.album = get_tag("TALB", "album", "\xa9alb", "ALBUM")
        if not result.album_artist:
            result.album_artist = get_tag("TPE2", "albumartist", "aART", "ALBUMARTIST")
        if not result.date:
            result.date = get_tag("TDRC", "TYER", "date", "\xa9day", "DATE", "YEAR")
        if not result.genre:
            result.genre = get_tag("TCON", "genre", "\xa9gen", "GENRE")
        if not result.track_number:
            result.track_number = get_tag("TRCK", "tracknumber", "trkn", "TRACKNUMBER")
        if not result.disc_number:
            result.disc_number = get_tag("TPOS", "discnumber", "disk", "DISCNUMBER")
        if not result.composer:
            result.composer = get_tag("TCOM", "composer", "\xa9wrt", "COMPOSER")
        if not result.publisher:
            result.publisher = get_tag("TPUB", "publisher", "organization", "ORGANIZATION", "LABEL")
        if not result.isrc:
            result.isrc = get_tag("TSRC", "isrc", "ISRC")
        if not result.bpm:
            result.bpm = get_tag("TBPM", "bpm", "tmpo", "BPM")
        if not result.copyright:
            result.copyright = get_tag("TCOP", "copyright", "cprt", "COPYRIGHT")
        if not result.comment:
            result.comment = get_tag("COMM::eng", "COMM", "comment", "\xa9cmt", "COMMENT")
        if not result.encoder:
            result.encoder = get_tag("TSSE", "encodedby", "\xa9too", "ENCODER")

        # Extract Embedded Artwork
        MetadataEngine._extract_artwork(m_file, result)

    @staticmethod
    def _extract_artwork(m_file: mutagen.FileType, result: FileMetadata) -> None:
        """Extract embedded image data, dimensions, and mime-type."""
        art_bytes = b""
        mime = "image/jpeg"
        desc = ""
        pic_type = "Front Cover"

        # ID3 APIC frames
        if hasattr(m_file, "tags") and m_file.tags is not None:
            for k, v in m_file.tags.items():
                if k.startswith("APIC"):
                    art_bytes = getattr(v, "data", b"")
                    mime = getattr(v, "mime", "image/jpeg")
                    desc = getattr(v, "desc", "")
                    pic_type = getattr(v, "type", "Front Cover")
                    if hasattr(pic_type, "name"):
                        pic_type = pic_type.name
                    break

        # FLAC pictures
        if not art_bytes and hasattr(m_file, "pictures") and m_file.pictures:
            pic = m_file.pictures[0]
            art_bytes = getattr(pic, "data", b"")
            mime = getattr(pic, "mime", "image/jpeg")
            desc = getattr(pic, "desc", "")
            pic_type = getattr(pic, "type", "Front Cover")
            if hasattr(pic_type, "name"):
                pic_type = pic_type.name

        # MP4 covr atom
        if not art_bytes and hasattr(m_file, "tags") and m_file.tags is not None:
            covr = m_file.tags.get("covr")
            if covr and isinstance(covr, list) and len(covr) > 0:
                art_bytes = bytes(covr[0])
                # Check magic bytes for PNG vs JPEG
                if art_bytes.startswith(b"\x89PNG"):
                    mime = "image/png"
                else:
                    mime = "image/jpeg"

        if art_bytes:
            w, h = 0, 0
            try:
                with Image.open(io.BytesIO(art_bytes)) as pil_img:
                    w, h = pil_img.size
            except Exception:
                pass

            result.artwork = EmbeddedArtwork(
                mime_type=mime,
                width=w,
                height=h,
                byte_size=len(art_bytes),
                picture_type=str(pic_type),
                description=str(desc),
                raw_data=art_bytes,
            )
