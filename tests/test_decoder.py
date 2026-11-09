"""Tests for UniversalAudioDecoder and Timecode calculation."""

import math
import os
import tempfile
import numpy as np
import scipy.io.wavfile as wav
import av

from src.core.decoder import UniversalAudioDecoder, samples_to_timecode


def test_samples_to_timecode():
    # 48000 Hz sample rate
    # Exactly 1 second at 24 fps = 00:00:01:00
    tc_24 = samples_to_timecode(48000, 48000, "24")
    assert tc_24 == "00:00:01:00"

    # Exactly 1 hour (48000 * 3600 samples)
    tc_hour = samples_to_timecode(48000 * 3600, 48000, "24")
    assert tc_hour == "01:00:00:00"

    # PAL 25 fps: 1 second = 00:00:01:00
    tc_25 = samples_to_timecode(48000, 48000, "25")
    assert tc_25 == "00:00:01:00"

    # SMPTE 29.97 DF (Drop Frame)
    tc_df = samples_to_timecode(48000 * 10, 48000, "29.97 DF")
    assert ";" in tc_df  # Drop frame uses semicolon delimiter


def test_wav_inspection_and_decoding():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        sr = 48000
        duration_s = 1.5
        n_samples = int(sr * duration_s)
        t = np.linspace(0, duration_s, n_samples, endpoint=False)
        # Stereo 440 Hz / 880 Hz sine wave
        audio_in = np.column_stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 880 * t)])
        wav.write(tmp_path, sr, (audio_in * 32767).astype(np.int16))

        # Inspect
        info = UniversalAudioDecoder.inspect(tmp_path)
        assert info.sample_rate == 48000
        assert info.channels == 2
        assert "pcm" in info.codec_name.lower()
        assert info.bit_depth == 16
        assert math.isclose(info.duration_seconds, 1.5, rel_tol=1e-2)

        # Decode
        decoded, decoded_sr, updated_info = UniversalAudioDecoder.decode_audio_array(tmp_path)
        assert decoded_sr == 48000
        assert decoded.shape == (n_samples, 2)
        assert decoded.dtype == np.float32
        assert np.max(np.abs(decoded)) <= 1.0

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
