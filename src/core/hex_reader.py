"""AudioScope Virtualized Memory-Mapped Binary Explorer & Container Chunk Parser.

Provides zero-copy, lazy-loading hex exploration using mmap and hierarchical
container chunk parsing for RIFF/WAVE, AIFF, MP3, FLAC, and MP4/M4A.
"""

from __future__ import annotations

import io
import math
import mmap
import os
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class ChunkNode:
    """Hierarchical container chunk or box."""
    name: str
    offset_start: int
    offset_end: int
    length: int
    description: str = ""
    details: Dict[str, str] = field(default_factory=dict)
    children: List["ChunkNode"] = field(default_factory=list)

    @property
    def offset_hex(self) -> str:
        return f"0x{self.offset_start:08X}"

    @property
    def length_formatted(self) -> str:
        if self.length < 1024:
            return f"{self.length} B"
        elif self.length < 1024 * 1024:
            return f"{self.length / 1024.0:.1f} KB"
        return f"{self.length / (1024.0 * 1024.0):.2f} MB"


class HexReader:
    """Zero-copy memory-mapped file reader for virtualized hex inspection."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_size = os.path.getsize(file_path)
        self._file: Optional[io.BufferedReader] = None
        self._mmap: Optional[mmap.mmap] = None

        if self.file_size > 0:
            self._file = open(file_path, "rb")
            self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)

        self.bytes_per_row = 16
        self.total_rows = math.ceil(self.file_size / self.bytes_per_row) if self.file_size > 0 else 0

    def close(self) -> None:
        """Close mmap and file handles."""
        if self._mmap is not None:
            try:
                self._mmap.close()
            except Exception:
                pass
            self._mmap = None
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None

    def __enter__(self) -> "HexReader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def get_row_data(self, row_idx: int) -> Tuple[int, bytes, str, str]:
        """Fetch row data on demand without loading whole file into memory.

        Returns: (offset, raw_bytes, hex_string_grouped, ascii_string)
        """
        if self._mmap is None or row_idx < 0 or row_idx >= self.total_rows:
            return 0, b"", "", ""

        offset = row_idx * self.bytes_per_row
        length = min(self.bytes_per_row, self.file_size - offset)
        raw = self._mmap[offset : offset + length]

        # Format hex with 8 + 8 grouping
        hex_tokens = [f"{b:02X}" for b in raw]
        if len(hex_tokens) > 8:
            hex_str = " ".join(hex_tokens[:8]) + "  " + " ".join(hex_tokens[8:])
        else:
            hex_str = " ".join(hex_tokens)

        # Pad hex representation to uniform column width (16 bytes = 47 chars)
        hex_padded = hex_str.ljust(48)

        # ASCII representation (. for non-printable characters 32..126)
        ascii_chars = [
            chr(b) if 32 <= b <= 126 else "."
            for b in raw
        ]
        ascii_str = "".join(ascii_chars)

        return offset, raw, hex_padded, ascii_str

    def search_pattern(self, pattern: bytes, start_offset: int = 0) -> int:
        """Search raw byte pattern in mmap. Returns match offset or -1."""
        if self._mmap is None or not pattern or start_offset >= self.file_size:
            return -1
        return self._mmap.find(pattern, max(0, start_offset))

    def search_pattern_reverse(self, pattern: bytes, start_offset: int) -> int:
        """Search backward for raw byte pattern in mmap. Returns match offset or -1."""
        if self._mmap is None or not pattern or start_offset <= 0:
            return -1
        return self._mmap.rfind(pattern, 0, min(self.file_size, start_offset))

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Read a slice of bytes from mmap."""
        if self._mmap is None or offset < 0 or offset >= self.file_size:
            return b""
        end = min(self.file_size, offset + length)
        return self._mmap[offset:end]


class ContainerChunkParser:
    """Parses binary container structures and returns a hierarchical ChunkNode tree."""

    @staticmethod
    def parse(file_path: str) -> List[ChunkNode]:
        """Auto-detect format and parse container chunks."""
        if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
            return []

        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            magic = f.read(16)

        # 1. RIFF / WAVE
        if magic.startswith(b"RIFF") or magic.startswith(b"RIFX") or magic.startswith(b"RF64"):
            return ContainerChunkParser._parse_riff(file_path, file_size)

        # 2. AIFF
        if magic.startswith(b"FORM"):
            return ContainerChunkParser._parse_aiff(file_path, file_size)

        # 3. FLAC
        if magic.startswith(b"fLaC"):
            return ContainerChunkParser._parse_flac(file_path, file_size)

        # 4. MP4 / M4A / MOV (ISO Base Media File Format)
        if len(magic) >= 8 and magic[4:8] in (b"ftyp", b"moov", b"wide", b"mdat"):
            return ContainerChunkParser._parse_mp4(file_path, file_size)

        # 5. MP3 (ID3v2 or MPEG Audio frame sync)
        if magic.startswith(b"ID3") or (len(magic) >= 2 and magic[0] == 0xFF and (magic[1] & 0xE0) == 0xE0):
            return ContainerChunkParser._parse_mp3(file_path, file_size)

        # Fallback generic container
        return [
            ChunkNode(
                name="Raw Audio / Unknown Container",
                offset_start=0,
                offset_end=file_size,
                length=file_size,
                description="Unrecognized container header or raw PCM payload",
            )
        ]

    @staticmethod
    def _parse_riff(file_path: str, file_size: int) -> List[ChunkNode]:
        """Parse RIFF/RF64/RIFX WAVE chunk tree."""
        root_nodes: List[ChunkNode] = []
        with open(file_path, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                return []

            riff_id = header[:4].decode("ascii", errors="replace")
            is_be = (header[:4] == b"RIFX")
            endian = ">" if is_be else "<"
            riff_size = struct.unpack(f"{endian}I", header[4:8])[0]
            format_id = header[8:12].decode("ascii", errors="replace")

            root = ChunkNode(
                name=f"{riff_id} Header",
                offset_start=0,
                offset_end=12,
                length=12,
                description=f"{riff_id} container, format: {format_id}",
                details={"Format": format_id, "Payload Size": f"{riff_size} bytes"},
            )
            root_nodes.append(root)

            # Parse sub-chunks
            offset = 12
            while offset < file_size:
                f.seek(offset)
                chunk_hdr = f.read(8)
                if len(chunk_hdr) < 8:
                    break

                chunk_id_bytes = chunk_hdr[:4]
                chunk_id = chunk_id_bytes.decode("ascii", errors="replace").strip()
                chunk_size = struct.unpack(f"{endian}I", chunk_hdr[4:8])[0]

                chunk_start = offset
                chunk_data_start = offset + 8
                chunk_data_end = min(file_size, chunk_data_start + chunk_size)
                chunk_total_len = 8 + chunk_size

                details: Dict[str, str] = {
                    "Chunk ID": chunk_id,
                    "Data Size": f"{chunk_size} bytes",
                    "Data Offset": f"0x{chunk_data_start:08X}",
                }

                desc = f"Chunk: {chunk_id}"
                children: List[ChunkNode] = []

                if chunk_id_bytes == b"fmt ":
                    desc = "WAVE Audio Format Specification"
                    fmt_bytes = f.read(min(chunk_size, 40))
                    if len(fmt_bytes) >= 16:
                        wFormatTag, nChannels, nSamplesPerSec, nAvgBytesPerSec, nBlockAlign, wBitsPerSample = (
                            struct.unpack(f"{endian}HHIIHH", fmt_bytes[:16])
                        )
                        fmt_type = "PCM" if wFormatTag == 1 else ("IEEE Float" if wFormatTag == 3 else f"Tag {wFormatTag}")
                        details["Audio Format"] = fmt_type
                        details["Channels"] = str(nChannels)
                        details["Sample Rate"] = f"{nSamplesPerSec} Hz"
                        details["Bits Per Sample"] = f"{wBitsPerSample}-bit"
                        details["Byte Rate"] = f"{nAvgBytesPerSec} B/s"

                elif chunk_id_bytes == b"bext":
                    desc = "Broadcast Wave Extension (BEXT) Chunk"
                    details["Standard"] = "EBU Tech 3285"

                elif chunk_id_bytes in (b"iXML", b"ixml"):
                    desc = "iXML Production Audio Metadata"
                    details["Format"] = "XML Track & Take Data"

                elif chunk_id_bytes == b"cart":
                    desc = "AES46-2002 CART Radio Automation"

                elif chunk_id_bytes == b"data":
                    desc = "Raw Audio Sample Payload"
                    details["Content"] = "Encoded / Uncompressed Audio Stream"

                elif chunk_id_bytes == b"fact":
                    desc = "Fact Chunk (Sample Count)"

                elif chunk_id_bytes == b"JUNK":
                    desc = "Alignment Padding / Junk"

                elif chunk_id_bytes == b"LIST":
                    list_type = f.read(4).decode("ascii", errors="replace")
                    desc = f"LIST Chunk ({list_type})"
                    details["List Type"] = list_type

                chunk_node = ChunkNode(
                    name=chunk_id or "Chunk",
                    offset_start=chunk_start,
                    offset_end=chunk_data_end,
                    length=chunk_total_len,
                    description=desc,
                    details=details,
                    children=children,
                )
                root_nodes.append(chunk_node)

                # Advance to next word-aligned offset
                padded_size = chunk_size + (chunk_size % 2)
                offset += 8 + padded_size

        return root_nodes

    @staticmethod
    def _parse_aiff(file_path: str, file_size: int) -> List[ChunkNode]:
        """Parse FORM AIFF chunk tree."""
        root_nodes: List[ChunkNode] = []
        with open(file_path, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                return []

            form_size = struct.unpack(">I", header[4:8])[0]
            form_type = header[8:12].decode("ascii", errors="replace")

            root = ChunkNode(
                name="FORM Header",
                offset_start=0,
                offset_end=12,
                length=12,
                description=f"AIFF FORM header ({form_type})",
                details={"Form Type": form_type, "Length": f"{form_size} bytes"},
            )
            root_nodes.append(root)

            offset = 12
            while offset < file_size:
                f.seek(offset)
                hdr = f.read(8)
                if len(hdr) < 8:
                    break

                cid = hdr[:4].decode("ascii", errors="replace").strip()
                csize = struct.unpack(">I", hdr[4:8])[0]
                data_start = offset + 8
                data_end = min(file_size, data_start + csize)

                desc = f"AIFF Chunk: {cid}"
                details = {"Chunk ID": cid, "Size": f"{csize} bytes"}

                if cid == "COMM":
                    desc = "Common Chunk (Channels, Sample Rate, Bit Depth)"
                elif cid == "SSND":
                    desc = "Sound Data Payload"
                elif cid == "MARK":
                    desc = "Marker Chunk"
                elif cid == "INST":
                    desc = "Instrument Chunk"

                chunk_node = ChunkNode(
                    name=cid or "Chunk",
                    offset_start=offset,
                    offset_end=data_end,
                    length=8 + csize,
                    description=desc,
                    details=details,
                )
                root_nodes.append(chunk_node)

                padded_size = csize + (csize % 2)
                offset += 8 + padded_size

        return root_nodes

    @staticmethod
    def _parse_flac(file_path: str, file_size: int) -> List[ChunkNode]:
        """Parse FLAC metadata blocks and audio stream."""
        nodes: List[ChunkNode] = []
        with open(file_path, "rb") as f:
            magic = f.read(4)
            if magic != b"fLaC":
                return []

            nodes.append(
                ChunkNode(
                    name="fLaC Marker",
                    offset_start=0,
                    offset_end=4,
                    length=4,
                    description="FLAC Stream Synchronization Marker (0x664C6143)",
                )
            )

            offset = 4
            is_last = False

            block_type_names = {
                0: "STREAMINFO",
                1: "PADDING",
                2: "APPLICATION",
                3: "SEEKTABLE",
                4: "VORBIS_COMMENT",
                5: "CUESHEET",
                6: "PICTURE",
            }

            while offset < file_size and not is_last:
                f.seek(offset)
                hdr = f.read(4)
                if len(hdr) < 4:
                    break

                flag_and_type = hdr[0]
                is_last = bool(flag_and_type & 0x80)
                block_type = flag_and_type & 0x7F
                block_len = (hdr[1] << 16) | (hdr[2] << 8) | hdr[3]

                type_name = block_type_names.get(block_type, f"CUSTOM ({block_type})")
                block_start = offset
                block_data_start = offset + 4
                block_end = min(file_size, block_data_start + block_len)

                details = {
                    "Block Type": type_name,
                    "Is Last Block": str(is_last),
                    "Data Size": f"{block_len} bytes",
                    "Data Offset": f"0x{block_data_start:08X}",
                }

                desc = f"Metadata Block: {type_name}"
                if block_type == 0:
                    desc = "Stream Specifications (Sample Rate, Channels, Bits, MD5)"
                elif block_type == 4:
                    desc = "VorbisComment User Tags"
                elif block_type == 6:
                    desc = "Embedded Cover Picture"

                nodes.append(
                    ChunkNode(
                        name=f"METADATA_{type_name}",
                        offset_start=block_start,
                        offset_end=block_end,
                        length=4 + block_len,
                        description=desc,
                        details=details,
                    )
                )

                offset = block_end

            # Remainder of file is Audio Frames
            if offset < file_size:
                nodes.append(
                    ChunkNode(
                        name="AUDIO_FRAMES",
                        offset_start=offset,
                        offset_end=file_size,
                        length=file_size - offset,
                        description="FLAC Compressed Audio Frames",
                        details={"Audio Payload Size": f"{file_size - offset} bytes"},
                    )
                )

        return nodes

    @staticmethod
    def _parse_mp3(file_path: str, file_size: int) -> List[ChunkNode]:
        """Parse MP3 ID3v2 header, audio frame sync words, Xing/LAME headers, and ID3v1."""
        nodes: List[ChunkNode] = []
        with open(file_path, "rb") as f:
            header = f.read(10)
            audio_start_offset = 0

            # 1. ID3v2 Header
            if header.startswith(b"ID3"):
                version_major = header[3]
                version_minor = header[4]
                flags = header[5]
                # Synchsafe integer (7 bits per byte)
                s_size = (
                    ((header[6] & 0x7F) << 21)
                    | ((header[7] & 0x7F) << 14)
                    | ((header[8] & 0x7F) << 7)
                    | (header[9] & 0x7F)
                )
                has_footer = bool(flags & 0x10)
                id3_total_len = 10 + s_size + (10 if has_footer else 0)
                audio_start_offset = id3_total_len

                nodes.append(
                    ChunkNode(
                        name=f"ID3v2.{version_major}.{version_minor} Header",
                        offset_start=0,
                        offset_end=id3_total_len,
                        length=id3_total_len,
                        description=f"ID3v2.{version_major} Metadata Container",
                        details={
                            "Version": f"2.{version_major}.{version_minor}",
                            "Tag Size": f"{s_size} bytes",
                            "Unsynch Flag": str(bool(flags & 0x80)),
                            "Extended Header": str(bool(flags & 0x40)),
                            "Footer Present": str(has_footer),
                        },
                    )
                )

            # 2. Search for first MPEG Audio Frame Sync (0xFFE or 0xFFF)
            f.seek(audio_start_offset)
            search_buf = f.read(min(65536, file_size - audio_start_offset))

            first_frame_pos = -1
            for i in range(len(search_buf) - 1):
                if search_buf[i] == 0xFF and (search_buf[i + 1] & 0xE0) == 0xE0:
                    first_frame_pos = audio_start_offset + i
                    break

            if first_frame_pos >= 0:
                # Check for Xing / Info / LAME / VBRI header inside the first frame
                f.seek(first_frame_pos)
                first_frame_bytes = f.read(1024)

                xing_pos = first_frame_bytes.find(b"Xing")
                info_pos = first_frame_bytes.find(b"Info")
                lame_pos = first_frame_bytes.find(b"LAME")
                vbri_pos = first_frame_bytes.find(b"VBRI")

                vbr_header_type = ""
                vbr_offset = -1
                if xing_pos >= 0:
                    vbr_header_type = "Xing (VBR)"
                    vbr_offset = first_frame_pos + xing_pos
                elif info_pos >= 0:
                    vbr_header_type = "Info (CBR)"
                    vbr_offset = first_frame_pos + info_pos
                elif vbri_pos >= 0:
                    vbr_header_type = "VBRI (Fraunhofer VBR)"
                    vbr_offset = first_frame_pos + vbri_pos

                if vbr_header_type:
                    nodes.append(
                        ChunkNode(
                            name=f"{vbr_header_type} Header",
                            offset_start=vbr_offset,
                            offset_end=vbr_offset + 120,
                            length=120,
                            description=f"MPEG Stream Header: {vbr_header_type}",
                            details={"LAME Detected": str(lame_pos >= 0)},
                        )
                    )

                audio_end = file_size
                # Check for ID3v1 at EOF - 128 bytes
                if file_size >= 128:
                    f.seek(file_size - 128)
                    id3v1_tag = f.read(3)
                    if id3v1_tag == b"TAG":
                        audio_end = file_size - 128

                nodes.append(
                    ChunkNode(
                        name="MPEG Audio Stream",
                        offset_start=first_frame_pos,
                        offset_end=audio_end,
                        length=audio_end - first_frame_pos,
                        description="MPEG Audio Frames (Layer III / II / I)",
                        details={
                            "First Frame Sync Offset": f"0x{first_frame_pos:08X}",
                            "Audio Payload Size": f"{audio_end - first_frame_pos} bytes",
                        },
                    )
                )

                if audio_end < file_size:
                    nodes.append(
                        ChunkNode(
                            name="ID3v1 Tag",
                            offset_start=file_size - 128,
                            offset_end=file_size,
                            length=128,
                            description="Legacy ID3v1 Tag (128 bytes at EOF)",
                        )
                    )

        return nodes

    @staticmethod
    def _parse_mp4(file_path: str, file_size: int) -> List[ChunkNode]:
        """Parse MP4/M4A ISO Base Media File Format box / atom tree."""
        root_nodes: List[ChunkNode] = []
        with open(file_path, "rb") as f:
            ContainerChunkParser._parse_mp4_boxes(f, 0, file_size, root_nodes, max_depth=4)
        return root_nodes

    @staticmethod
    def _parse_mp4_boxes(
        f: io.BufferedReader,
        offset: int,
        end_offset: int,
        node_list: List[ChunkNode],
        max_depth: int = 4,
    ) -> None:
        """Recursively parse MP4 box tree."""
        if max_depth <= 0:
            return

        container_box_types = {
            "moov", "trak", "mdia", "minf", "stbl", "udta", "meta", "ilst"
        }

        descriptions = {
            "ftyp": "File Type & Brand Compatibility",
            "moov": "Movie Resource Container",
            "mvhd": "Movie Header (Duration, TimeScale)",
            "trak": "Track Container",
            "tkhd": "Track Header",
            "mdia": "Media Information Container",
            "mdhd": "Media Header",
            "hdlr": "Handler Reference (e.g. soun, vide)",
            "minf": "Media Information",
            "stbl": "Sample Table Container",
            "stsd": "Sample Description (Codec, Channels, Sample Rate)",
            "stts": "Time-to-Sample Table",
            "stsc": "Sample-to-Chunk Table",
            "stsz": "Sample Size Table",
            "stco": "Chunk Offset Table (32-bit)",
            "co64": "Chunk Offset Table (64-bit)",
            "mdat": "Media Data Audio/Video Payload",
            "udta": "User Data Container",
            "meta": "Metadata Container",
            "ilst": "iTunes Metadata Item List",
        }

        curr = offset
        while curr < end_offset:
            f.seek(curr)
            hdr = f.read(8)
            if len(hdr) < 8:
                break

            box_size = struct.unpack(">I", hdr[:4])[0]
            box_type = hdr[4:8].decode("latin-1", errors="replace")
            header_size = 8

            if box_size == 1:
                # 64-bit size follows
                ext_hdr = f.read(8)
                if len(ext_hdr) < 8:
                    break
                box_size = struct.unpack(">Q", ext_hdr)[0]
                header_size = 16
            elif box_size == 0:
                # Extends to EOF
                box_size = end_offset - curr

            if box_size < header_size:
                break

            box_start = curr
            box_end = min(end_offset, curr + box_size)
            data_start = curr + header_size
            data_size = box_end - data_start

            desc = descriptions.get(box_type, f"Atom: {box_type}")
            details = {
                "Atom Type": box_type,
                "Total Size": f"{box_size} bytes",
                "Payload Size": f"{data_size} bytes",
                "Offset": f"0x{box_start:08X}",
            }

            node = ChunkNode(
                name=box_type,
                offset_start=box_start,
                offset_end=box_end,
                length=box_size,
                description=desc,
                details=details,
            )
            node_list.append(node)

            # If container box, recursively parse children
            if box_type in container_box_types:
                # Special case: 'meta' atom has 4 bytes of version/flags before boxes
                child_start = data_start
                if box_type == "meta":
                    child_start += 4

                ContainerChunkParser._parse_mp4_boxes(
                    f, child_start, box_end, node.children, max_depth - 1
                )

            curr = box_end
