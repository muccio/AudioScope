"""Tests for AudioAnalyzer: ITU-R BS.1770-4, 4x True Peak, RMS, and Compliance."""

import math
import numpy as np
import pytest

from src.core.analyzer import AudioAnalyzer, linear_to_db


def test_true_peak_intersample_detection():
    # Signal with intersample peak: adjacent high samples
    sr = 48000
    sig = np.array([[0.0], [0.95], [0.95], [0.0]], dtype=np.float32)

    tp_dbtp, tp_channels = AudioAnalyzer.compute_true_peak(sig, sr)
    sample_peak_dbfs = linear_to_db(float(np.max(np.abs(sig))))

    # True peak with 4x oversampling should detect higher level than sample peak
    assert tp_dbtp > sample_peak_dbfs


def test_audio_analyzer_sine_wave():
    sr = 48000
    duration = 2.0
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    # 1 kHz stereo sine wave at 0.5 amplitude (-6.02 dBFS)
    ch1 = 0.5 * np.sin(2 * np.pi * 1000 * t)
    ch2 = 0.5 * np.sin(2 * np.pi * 1000 * t)
    stereo_data = np.column_stack([ch1, ch2]).astype(np.float32)

    metrics = AudioAnalyzer.analyze(stereo_data, sr)

    # Sample peak should be ~ -6.02 dBFS
    assert math.isclose(metrics.sample_peak_dbfs, -6.02, abs_tol=0.2)

    # RMS for sine with amplitude 0.5 is 0.5 / sqrt(2) = 0.35355 -> -9.03 dBFS
    assert math.isclose(metrics.rms_dbfs, -9.03, abs_tol=0.2)

    # Crest factor = sample peak - RMS ~ 3.01 dB
    assert math.isclose(metrics.crest_factor_db, 3.01, abs_tol=0.2)

    # DC offset should be virtually zero
    assert max(metrics.dc_offset_percent) < 0.05

    # Check compliance standards exist
    assert "EBU R128" in metrics.compliance
    assert "ATSC A/85" in metrics.compliance
    assert "Spotify" in metrics.compliance
    assert "Apple Music" in metrics.compliance

    ebu = metrics.compliance["EBU R128"]
    assert ebu.target_lufs == -23.0
    assert ebu.target_tp == -1.0


def test_silence_handling():
    sr = 48000
    silence = np.zeros((48000, 2), dtype=np.float32)
    metrics = AudioAnalyzer.analyze(silence, sr)
    assert metrics.integrated_lufs <= -69.0
    assert metrics.sample_peak_dbfs <= -100.0
