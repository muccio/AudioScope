"""Tests for HexReader and ContainerChunkParser."""

import os
import struct
import tempfile
import scipy.io.wavfile as wav
import numpy as np
import av

from src.core.hex_reader import HexReader, ContainerChunkParser


def test_hex_reader_zero_copy_mmap():
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Write 48 test bytes (3 rows)
        payload = bytes([i % 256 for i in range(48)])
        with open(tmp_path, "wb") as f:
            f.write(payload)

        with HexReader(tmp_path) as reader:
            assert reader.total_rows == 3
            assert reader.file_size == 48

            offset, raw, hex_str, ascii_str = reader.get_row_data(0)
            assert offset == 0
            assert len(raw) == 16
            assert hex_str.startswith("00 01 02 03")

            # Test byte search
            pos = reader.search_pattern(b"\x04\x05\x06")
            assert pos == 4

            # Reverse search
            rpos = reader.search_pattern_reverse(b"\x04\x05\x06", 20)
            assert rpos == 4

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_container_chunk_parser_riff():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        sr = 44100
        data = np.zeros((1000, 1), dtype=np.int16)
        wav.write(tmp_path, sr, data)

        chunks = ContainerChunkParser.parse(tmp_path)
        assert len(chunks) >= 3

        chunk_names = [c.name for c in chunks]
        assert "RIFF Header" in chunk_names
        assert "fmt" in chunk_names
        assert "data" in chunk_names

        # fmt chunk details
        fmt_chunk = next(c for c in chunks if c.name == "fmt")
        assert "Audio Format" in fmt_chunk.details
        assert "Sample Rate" in fmt_chunk.details
        assert fmt_chunk.details["Sample Rate"] == "44100 Hz"

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_container_chunk_parser_flac():
    with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        sr = 48000
        audio = (np.sin(np.linspace(0, 1, sr)) * 32767).astype(np.int16)
        with av.open(tmp_path, mode="w") as container:
            stream = container.add_stream("flac", rate=sr)
            stream.layout = "mono"
            frame = av.AudioFrame.from_ndarray(audio.reshape(1, -1), format="s16", layout="mono")
            frame.rate = sr
            for packet in stream.encode(frame):
                container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)

        chunks = ContainerChunkParser.parse(tmp_path)
        chunk_names = [c.name for c in chunks]
        assert "fLaC Marker" in chunk_names
        assert "METADATA_STREAMINFO" in chunk_names
        assert "AUDIO_FRAMES" in chunk_names

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_container_chunk_parser_mp3():
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        sr = 48000
        audio = (np.sin(np.linspace(0, 1, sr)) * 32767).astype(np.int16)
        with av.open(tmp_path, mode="w") as container:
            stream = container.add_stream("mp3", rate=sr)
            stream.layout = "mono"
            frame = av.AudioFrame.from_ndarray(audio.reshape(1, -1), format="s16", layout="mono")
            frame.rate = sr
            for packet in stream.encode(frame):
                container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)

        chunks = ContainerChunkParser.parse(tmp_path)
        assert len(chunks) >= 2
        chunk_names = [c.name for c in chunks]
        assert any("ID3" in name or "MPEG" in name or "Info" in name for name in chunk_names)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
