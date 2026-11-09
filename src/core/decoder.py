"""AudioScope Universal Stream Demuxer & Decoder.

Powered by PyAV (FFmpeg C-bindings) for container and codec inspection,
stream metadata extraction, and sample decoding.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any

import av
import numpy as np


@dataclass
class StreamInfo:
    """Detailed audio stream and container specifications."""
    file_path: str
    file_name: str
    file_size_bytes: int
    container_name: str
    container_long_name: str
    codec_name: str
    codec_long_name: str
    profile: Optional[str]
    sample_rate: int
    bit_depth: int
    sample_format: str
    channels: int
    channel_layout: str
    duration_seconds: float
    duration_samples: int
    nominal_bitrate: Optional[int]
    container_bitrate: Optional[int]
    calculated_bitrate: int
    is_vbr: bool
    uncompressed_size_bytes: int
    compression_ratio: float
    raw_metadata: Dict[str, str] = field(default_factory=dict)

    def formatted_duration(self) -> str:
        """Format duration as HH:MM:SS.mmm."""
        total_ms = int(self.duration_seconds * 1000)
        ms = total_ms % 1000
        total_sec = total_ms // 1000
        sec = total_sec % 60
        total_min = total_sec // 60
        minute = total_min % 60
        hour = total_min // 60
        return f"{hour:02d}:{minute:02d}:{sec:02d}.{ms:03d}"

    def formatted_timecode(self, fps: str = "24") -> str:
        """Format duration as SMPTE timecode HH:MM:SS:FF or HH:MM:SS;FF (drop-frame)."""
        return samples_to_timecode(self.duration_samples, self.sample_rate, fps)


def samples_to_timecode(total_samples: int, sample_rate: int, fps_mode: str = "24") -> str:
    """Convert sample count to SMPTE timecode string given a frame rate mode."""
    if sample_rate <= 0 or total_samples < 0:
        return "00:00:00:00"

    duration_sec = total_samples / float(sample_rate)

    if fps_mode == "29.97 DF":
        # SMPTE 12M drop-frame calculation
        # 29.97 fps = 30000 / 1001 fps
        # In DF, frame numbers 0 and 1 are dropped at the start of each minute,
        # EXCEPT when the minute number is divisible by 10 (0, 10, 20, 30, 40, 50).
        # Total frames dropped per 10 minutes = 9 * 2 = 18 frames.
        nominal_fps = 30
        frames_per_minute = 1800 - 2 # 1798
        frames_per_10min = 17980

        # Total running frame count at 29.97
        total_nominal_frames = int(math.floor(duration_sec * (30000.0 / 1001.0)))

        d = total_nominal_frames // frames_per_10min
        m = total_nominal_frames % frames_per_10min

        if m >= 2:
            frame_num = total_nominal_frames + 18 * d + 2 * ((m - 2) // 1798)
        else:
            frame_num = total_nominal_frames + 18 * d

        ff = frame_num % nominal_fps
        ss = (frame_num // nominal_fps) % 60
        mm = (frame_num // (nominal_fps * 60)) % 60
        hh = (frame_num // (nominal_fps * 3600)) % 24
        return f"{hh:02d}:{mm:02d}:{ss:02d};{ff:02d}"

    # Non-drop frame modes
    fps_map = {
        "23.976": 24000.0 / 1001.0,
        "24": 24.0,
        "25": 25.0,
        "29.97 NDF": 30000.0 / 1001.0,
        "30": 30.0,
        "48": 48.0,
        "50": 50.0,
        "59.94": 60000.0 / 1001.0,
        "60": 60.0,
    }
    fps = fps_map.get(fps_mode, 24.0)
    total_frames = int(math.floor(duration_sec * fps))

    rounded_fps = int(round(fps))
    ff = total_frames % rounded_fps
    total_sec = total_frames // rounded_fps
    ss = total_sec % 60
    total_min = total_sec // 60
    mm = total_min % 60
    hh = (total_min // 60) % 24
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


class UniversalAudioDecoder:
    """Universal audio decoder and container inspector using PyAV."""

    @staticmethod
    def inspect(file_path: str) -> StreamInfo:
        """Inspect file and return detailed StreamInfo without full decoding."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        with av.open(file_path) as container:
            # Find primary audio stream
            audio_stream = None
            for s in container.streams:
                if s.type == "audio":
                    audio_stream = s
                    break

            if audio_stream is None:
                raise ValueError(f"No audio stream found in file: {file_name}")

            container_name = container.format.name or "unknown"
            container_long_name = container.format.long_name or container_name
            codec_name = audio_stream.codec_context.name or audio_stream.name or "unknown"
            codec_long_name = (
                getattr(audio_stream.codec_context.codec, "long_name", None)
                or codec_name
            )
            profile = getattr(audio_stream, "profile", None)

            sample_rate = audio_stream.rate or 44100
            channels = audio_stream.channels or 2
            channel_layout = (
                getattr(audio_stream.layout, "name", None)
                or f"{channels} channels"
            )

            # Sample format & bit depth resolution
            fmt_obj = getattr(audio_stream, "format", None)
            sample_fmt_name = getattr(fmt_obj, "name", "unknown") if fmt_obj else "unknown"
            
            # Estimate bit depth
            bit_depth = 16
            if fmt_obj and hasattr(fmt_obj, "bits") and fmt_obj.bits > 0:
                bit_depth = fmt_obj.bits
            elif "24" in codec_name or "s24" in sample_fmt_name:
                bit_depth = 24
            elif "32" in codec_name or "s32" in sample_fmt_name or "flt" in sample_fmt_name:
                bit_depth = 32
            elif "64" in codec_name or "dbl" in sample_fmt_name:
                bit_depth = 64
            elif "8" in codec_name or "u8" in sample_fmt_name or "s8" in sample_fmt_name:
                bit_depth = 8

            # Duration calculation
            duration_sec = 0.0
            if audio_stream.duration is not None and audio_stream.time_base is not None:
                duration_sec = float(audio_stream.duration * audio_stream.time_base)
            elif container.duration is not None:
                duration_sec = float(container.duration) / float(av.AV_TIME_BASE)

            duration_samples = int(round(duration_sec * sample_rate))

            # Bitrates
            nominal_bitrate = audio_stream.bit_rate or None
            container_bitrate = container.bit_rate or None
            calculated_bitrate = int(
                (file_size * 8.0) / duration_sec
            ) if duration_sec > 0 else 0

            # VBR detection
            is_vbr = False
            lower_codec = codec_name.lower()
            if any(lossless in lower_codec for lossless in ["flac", "alac", "ape", "wavpack"]):
                is_vbr = True
            elif nominal_bitrate and calculated_bitrate:
                # If calculated bitrate differs by > 8% from nominal bitrate, likely VBR
                if abs(calculated_bitrate - nominal_bitrate) / nominal_bitrate > 0.08:
                    is_vbr = True
            elif any(vbr_format in container_name.lower() for vbr_format in ["ogg", "opus", "mp3", "aac", "m4a"]):
                if not nominal_bitrate or abs(calculated_bitrate - (nominal_bitrate or 0)) > 5000:
                    is_vbr = True

            # Uncompressed size & compression ratio
            bytes_per_sample = max(1, bit_depth // 8)
            uncompressed_size = duration_samples * channels * bytes_per_sample
            if file_size > 0:
                compression_ratio = uncompressed_size / float(file_size)
            else:
                compression_ratio = 1.0

            # Container & stream metadata tags
            raw_metadata: Dict[str, str] = {}
            if container.metadata:
                for k, v in container.metadata.items():
                    raw_metadata[str(k)] = str(v)
            if audio_stream.metadata:
                for k, v in audio_stream.metadata.items():
                    raw_metadata[f"stream_{k}"] = str(v)

            return StreamInfo(
                file_path=file_path,
                file_name=file_name,
                file_size_bytes=file_size,
                container_name=container_name,
                container_long_name=container_long_name,
                codec_name=codec_name,
                codec_long_name=codec_long_name,
                profile=profile,
                sample_rate=sample_rate,
                bit_depth=bit_depth,
                sample_format=sample_fmt_name,
                channels=channels,
                channel_layout=channel_layout,
                duration_seconds=duration_sec,
                duration_samples=duration_samples,
                nominal_bitrate=nominal_bitrate,
                container_bitrate=container_bitrate,
                calculated_bitrate=calculated_bitrate,
                is_vbr=is_vbr,
                uncompressed_size_bytes=uncompressed_size,
                compression_ratio=compression_ratio,
                raw_metadata=raw_metadata,
            )

    @staticmethod
    def decode_audio_array(
        file_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[np.ndarray, int, StreamInfo]:
        """Decode entire audio stream into a normalized float32 ndarray (samples, channels).

        Utilizes av.AudioResampler to normalize any format (s16, s24, s32, flt, etc.)
        to planar float32 [-1.0, 1.0].
        """
        info = UniversalAudioDecoder.inspect(file_path)

        with av.open(file_path) as container:
            audio_stream = next(s for s in container.streams if s.type == "audio")
            resampler = av.AudioResampler(format="fltp")

            chunks: List[np.ndarray] = []
            decoded_samples = 0
            expected_samples = max(1, info.duration_samples)

            if progress_callback:
                progress_callback(0.05, f"Decoding {info.file_name}...")

            for packet in container.demux(audio_stream):
                if cancel_check and cancel_check():
                    raise InterruptedError("Audio decoding canceled by user")

                for frame in packet.decode():
                    if frame is None:
                        continue
                    resampled_frames = resampler.resample(frame)
                    for rf in resampled_frames:
                        # rf.to_ndarray() is (channels, samples)
                        arr = rf.to_ndarray()
                        chunks.append(arr)
                        decoded_samples += arr.shape[1]

                    if progress_callback and decoded_samples % (info.sample_rate * 2) < 4096:
                        pct = min(0.60, 0.05 + 0.55 * (decoded_samples / expected_samples))
                        progress_callback(pct, f"Decoding audio: {decoded_samples:,} samples...")

            # Flush resampler buffer
            flushed = resampler.resample(None)
            if flushed:
                for rf in flushed:
                    arr = rf.to_ndarray()
                    chunks.append(arr)
                    decoded_samples += arr.shape[1]

            if not chunks:
                raise ValueError("No audio frames could be decoded from this file.")

            # Concatenate chunks along sample axis: (channels, total_samples)
            full_channels_first = np.concatenate(chunks, axis=1)

            # Transpose to standard (samples, channels)
            audio_data = np.ascontiguousarray(full_channels_first.T, dtype=np.float32)

            # Update actual measured samples and duration
            actual_samples = audio_data.shape[0]
            if actual_samples != info.duration_samples and actual_samples > 0:
                info.duration_samples = actual_samples
                info.duration_seconds = actual_samples / float(info.sample_rate)
                bytes_per_sample = max(1, info.bit_depth // 8)
                info.uncompressed_size_bytes = actual_samples * info.channels * bytes_per_sample
                if info.file_size_bytes > 0:
                    info.compression_ratio = info.uncompressed_size_bytes / float(info.file_size_bytes)
                info.calculated_bitrate = int((info.file_size_bytes * 8.0) / info.duration_seconds)

            if progress_callback:
                progress_callback(0.60, f"Decoded {actual_samples:,} samples successfully.")

            return audio_data, info.sample_rate, info
