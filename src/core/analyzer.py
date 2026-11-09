"""AudioScope Broadcast Signal & Loudness Analyzer.

Implements ITU-R BS.1770-4, EBU R128, EBU Tech 3342 Loudness Range (LRA),
Annex 2 4x Oversampled True Peak (dBTP), Sample Peak, RMS, Crest Factor,
and Standard Compliance Matrix evaluation.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pyloudnorm as pyln
from scipy.ndimage import uniform_filter1d
import scipy.signal as signal


@dataclass
class ComplianceItem:
    """Standard compliance evaluation result."""
    standard_name: str
    target_lufs: float
    tolerance_lu: float
    measured_lufs: float
    lufs_delta: float
    lufs_pass: bool
    target_tp: float
    measured_tp: float
    tp_pass: bool
    target_short_term: Optional[float]
    measured_short_term: float
    short_term_pass: bool
    overall_pass: bool
    status_text: str
    notes: str


@dataclass
class AudioMetrics:
    """Exhaustive broadcast loudness and dynamic metrics."""
    # ITU-R BS.1770-4 / EBU R128 Loudness
    integrated_lufs: float
    loudness_range_lu: float
    max_short_term_lufs: float
    max_momentary_lufs: float

    # Peak & Dynamic Metrics
    true_peak_dbtp: float
    true_peak_channels: List[float]
    sample_peak_dbfs: float
    sample_peak_channels: List[float]
    rms_dbfs: float
    rms_channels: List[float]
    crest_factor_db: float

    # DC Offset
    dc_offset_amplitude: List[float]
    dc_offset_percent: List[float]

    # Compliance Matrix
    compliance: Dict[str, ComplianceItem] = field(default_factory=dict)

    # Benchmark stats
    analysis_duration_sec: float = 0.0
    realtime_factor: float = 0.0


class AudioAnalyzer:
    """High-performance vectorized audio signal analyzer."""

    @staticmethod
    def analyze(
        audio_data: np.ndarray,
        sample_rate: int,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> AudioMetrics:
        """Perform exhaustive broadcast loudness and peak measurement.

        audio_data: np.ndarray with shape (n_samples, n_channels) or (n_samples,)
        """
        start_time = time.time()

        if audio_data.ndim == 1:
            audio_data = audio_data[:, np.newaxis]

        n_samples, n_channels = audio_data.shape
        audio_duration_sec = n_samples / float(sample_rate) if sample_rate > 0 else 0.0

        if n_samples == 0:
            raise ValueError("Audio data is empty")

        if cancel_check and cancel_check():
            raise InterruptedError("Analysis canceled")

        if progress_callback:
            progress_callback(0.65, "Calculating Sample Peak, RMS, and DC Offset...")

        # 1. Sample Peak (dBFS)
        abs_data = np.abs(audio_data)
        sample_peak_linear_per_ch = np.max(abs_data, axis=0)
        sample_peak_global = float(np.max(sample_peak_linear_per_ch))

        sample_peak_channels = [
            linear_to_db(pk) for pk in sample_peak_linear_per_ch
        ]
        sample_peak_dbfs = linear_to_db(sample_peak_global)

        # 2. RMS (dBFS)
        sq_mean_per_ch = np.mean(audio_data ** 2, axis=0)
        rms_linear_per_ch = np.sqrt(sq_mean_per_ch)
        rms_linear_global = math.sqrt(float(np.mean(sq_mean_per_ch)))

        rms_channels = [linear_to_db(rms) for rms in rms_linear_per_ch]
        rms_dbfs = linear_to_db(rms_linear_global)

        # 3. Crest Factor (dB)
        crest_factor_db = sample_peak_dbfs - rms_dbfs

        # 4. DC Offset
        mean_offset_per_ch = np.mean(audio_data, axis=0)
        dc_offset_amplitude = [float(v) for v in mean_offset_per_ch]
        dc_offset_percent = [float(abs(v) * 100.0) for v in mean_offset_per_ch]

        if cancel_check and cancel_check():
            raise InterruptedError("Analysis canceled")

        # 5. True Peak 4x oversampling interpolation (ITU-R BS.1770-4 Annex 2)
        if progress_callback:
            progress_callback(0.72, "Computing 4x Oversampled True Peak (ITU-R BS.1770-4)...")

        true_peak_dbtp, true_peak_channels = AudioAnalyzer.compute_true_peak(
            audio_data, sample_rate, cancel_check=cancel_check
        )

        if cancel_check and cancel_check():
            raise InterruptedError("Analysis canceled")

        # 6. Integrated Loudness (LUFS) & Loudness Range (LRA) via pyloudnorm
        if progress_callback:
            progress_callback(0.82, "Calculating Integrated Loudness (LUFS) and LRA...")

        meter = pyln.Meter(sample_rate)
        # pyloudnorm supports mono, stereo, or up to 5 channels
        calc_data = audio_data if n_channels <= 5 else audio_data[:, :5]

        try:
            integrated_lufs = float(meter.integrated_loudness(calc_data))
            if math.isinf(integrated_lufs) or math.isnan(integrated_lufs):
                integrated_lufs = -70.0
        except Exception:
            integrated_lufs = -70.0

        try:
            loudness_range_lu = float(meter.loudness_range(calc_data))
            if math.isnan(loudness_range_lu) or math.isinf(loudness_range_lu):
                loudness_range_lu = 0.0
        except Exception:
            loudness_range_lu = 0.0

        if cancel_check and cancel_check():
            raise InterruptedError("Analysis canceled")

        # 7. Momentary (400ms) & Short-term (3.0s) Loudness
        if progress_callback:
            progress_callback(0.90, "Evaluating Short-Term & Momentary Sliding Windows...")

        max_momentary, max_short_term = AudioAnalyzer.compute_momentary_and_short_term(
            calc_data, sample_rate, meter
        )

        # 8. Standard Compliance Matrix
        metrics = AudioMetrics(
            integrated_lufs=round(integrated_lufs, 2),
            loudness_range_lu=round(loudness_range_lu, 2),
            max_short_term_lufs=round(max_short_term, 2),
            max_momentary_lufs=round(max_momentary, 2),
            true_peak_dbtp=round(true_peak_dbtp, 2),
            true_peak_channels=[round(tp, 2) for tp in true_peak_channels],
            sample_peak_dbfs=round(sample_peak_dbfs, 2),
            sample_peak_channels=[round(sp, 2) for sp in sample_peak_channels],
            rms_dbfs=round(rms_dbfs, 2),
            rms_channels=[round(r, 2) for r in rms_channels],
            crest_factor_db=round(crest_factor_db, 2),
            dc_offset_amplitude=dc_offset_amplitude,
            dc_offset_percent=[round(dc, 4) for dc in dc_offset_percent],
        )

        metrics.compliance = AudioAnalyzer.evaluate_compliance(metrics)

        elapsed = time.time() - start_time
        metrics.analysis_duration_sec = elapsed
        metrics.realtime_factor = (
            audio_duration_sec / elapsed if elapsed > 0 else 0.0
        )

        if progress_callback:
            progress_callback(1.0, f"Analysis complete ({metrics.realtime_factor:.1f}x realtime)")

        return metrics

    @staticmethod
    def compute_true_peak(
        audio_data: np.ndarray,
        sample_rate: int,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[float, List[float]]:
        """Calculate True Peak (dBTP) using 4x polyphase oversampling interpolation.

        Vectorized and chunked for constant memory and high performance.
        """
        # Determine oversampling factor per BS.1770-4:
        # <= 48 kHz: 4x
        # 88.2 - 96 kHz: 2x
        # > 96 kHz: 1x (direct)
        if sample_rate <= 48000:
            up_factor = 4
        elif sample_rate <= 96000:
            up_factor = 2
        else:
            up_factor = 1

        n_samples, n_channels = audio_data.shape
        max_peaks_per_channel = np.zeros(n_channels, dtype=np.float64)

        if up_factor == 1:
            max_peaks_per_channel = np.max(np.abs(audio_data), axis=0)
        else:
            # Chunk size: 256k samples per chunk to balance memory and speed
            chunk_size = 262144
            overlap = 64  # Boundary padding for filter stabilization

            for start in range(0, n_samples, chunk_size):
                if cancel_check and cancel_check():
                    raise InterruptedError("Analysis canceled")

                chunk_start = max(0, start - overlap)
                chunk_end = min(n_samples, start + chunk_size + overlap)
                sub_chunk = audio_data[chunk_start:chunk_end]

                # Polyphase resampling along time axis (axis=0)
                oversampled = signal.resample_poly(sub_chunk, up_factor, 1, axis=0)

                # Trim boundaries if padded
                trim_start = (start - chunk_start) * up_factor
                actual_len = (min(start + chunk_size, n_samples) - start) * up_factor
                valid_samples = oversampled[trim_start : trim_start + actual_len]

                if valid_samples.size > 0:
                    chunk_peaks = np.max(np.abs(valid_samples), axis=0)
                    max_peaks_per_channel = np.maximum(max_peaks_per_channel, chunk_peaks)

        global_max_linear = float(np.max(max_peaks_per_channel))
        true_peak_dbtp = linear_to_db(global_max_linear)
        true_peak_channels = [linear_to_db(pk) for pk in max_peaks_per_channel]

        return true_peak_dbtp, true_peak_channels

    @staticmethod
    def compute_momentary_and_short_term(
        audio_data: np.ndarray,
        sample_rate: int,
        meter: pyln.Meter,
    ) -> Tuple[float, float]:
        """Compute maximum momentary (400ms) and short-term (3.0s) loudness."""
        n_samples, n_channels = audio_data.shape

        # Channel weighting coefficients per ITU-R BS.1770:
        # Left (1.0), Right (1.0), Center (1.0), Left Surround (1.41), Right Surround (1.41)
        channel_weights = [1.0, 1.0, 1.0, 1.41, 1.41][:n_channels]
        weights = np.array(channel_weights, dtype=np.float32)

        # Apply K-weighting filter (high-shelf followed by high-pass)
        k_filtered = np.zeros_like(audio_data, dtype=np.float32)
        for ch in range(n_channels):
            hs = meter._filters["high_shelf"].apply_filter(audio_data[:, ch])
            k_filtered[:, ch] = meter._filters["high_pass"].apply_filter(hs)

        # Weighted squared sum across channels: shape (n_samples,)
        sq = (k_filtered ** 2) @ weights

        # Sliding window sizes
        win_m = max(1, int(0.400 * sample_rate))  # 400 ms momentary
        win_s = max(1, int(3.000 * sample_rate))  # 3000 ms short-term

        eps = 1e-12

        # Momentary window average
        m_mean = uniform_filter1d(sq, size=win_m, mode="constant", origin=-win_m // 2)
        valid_m = m_mean[win_m:] if len(m_mean) > win_m else m_mean
        if len(valid_m) > 0 and np.max(valid_m) > eps:
            max_m_linear = float(np.max(valid_m))
            max_momentary = -0.691 + 10.0 * math.log10(max(eps, max_m_linear))
        else:
            max_momentary = -70.0

        # Short-term window average
        s_mean = uniform_filter1d(sq, size=win_s, mode="constant", origin=-win_s // 2)
        valid_s = s_mean[win_s:] if len(s_mean) > win_s else s_mean
        if len(valid_s) > 0 and np.max(valid_s) > eps:
            max_s_linear = float(np.max(valid_s))
            max_short_term = -0.691 + 10.0 * math.log10(max(eps, max_s_linear))
        else:
            max_short_term = -70.0

        return max_momentary, max_short_term

    @staticmethod
    def evaluate_compliance(metrics: AudioMetrics) -> Dict[str, ComplianceItem]:
        """Evaluate compliance against international broadcast and streaming standards."""
        standards_def = [
            {
                "id": "EBU R128",
                "name": "EBU R128 (European Broadcast)",
                "target_lufs": -23.0,
                "tolerance_lu": 0.5,
                "target_tp": -1.0,
                "target_short_term": -18.0,
                "notes": "Target: -23.0 LUFS (±0.5 LU), Max True Peak: -1.0 dBTP, Max Short-Term: -18.0 LUFS",
            },
            {
                "id": "ATSC A/85",
                "name": "ATSC A/85 (US Television / CALM Act)",
                "target_lufs": -24.0,
                "tolerance_lu": 1.0,
                "target_tp": -2.0,
                "target_short_term": None,
                "notes": "Target: -24.0 LKFS (±1.0 LU), Max True Peak: -2.0 dBTP",
            },
            {
                "id": "Spotify",
                "name": "Spotify / YouTube / Streaming (Normal)",
                "target_lufs": -14.0,
                "tolerance_lu": 1.0,
                "target_tp": -1.0,
                "target_short_term": None,
                "notes": "Target: -14.0 LUFS, Max True Peak: -1.0 dBTP (-2.0 dBTP recommended for lossy)",
            },
            {
                "id": "Apple Music",
                "name": "Apple Music (Sound Check)",
                "target_lufs": -16.0,
                "tolerance_lu": 1.0,
                "target_tp": -1.0,
                "target_short_term": None,
                "notes": "Target: -16.0 LUFS (±1.0 LU), Max True Peak: -1.0 dBTP",
            },
            {
                "id": "Amazon Music",
                "name": "Amazon Music / Tidal",
                "target_lufs": -14.0,
                "tolerance_lu": 1.0,
                "target_tp": -1.0,
                "target_short_term": None,
                "notes": "Target: -14.0 LUFS (±1.0 LU), Max True Peak: -1.0 dBTP",
            },
            {
                "id": "Netflix",
                "name": "Netflix Audio Delivery",
                "target_lufs": -27.0,
                "tolerance_lu": 1.0,
                "target_tp": -2.0,
                "target_short_term": None,
                "notes": "Target: -27.0 LUFS dialogue / overall, Max True Peak: -2.0 dBTP",
            },
        ]

        results: Dict[str, ComplianceItem] = {}

        for std in standards_def:
            target_lufs = std["target_lufs"]
            tolerance = std["tolerance_lu"]
            measured_lufs = metrics.integrated_lufs
            lufs_delta = round(measured_lufs - target_lufs, 2)
            lufs_pass = abs(lufs_delta) <= tolerance

            target_tp = std["target_tp"]
            measured_tp = metrics.true_peak_dbtp
            tp_pass = measured_tp <= target_tp

            target_st = std["target_short_term"]
            measured_st = metrics.max_short_term_lufs
            if target_st is not None:
                st_pass = measured_st <= target_st
            else:
                st_pass = True

            overall_pass = lufs_pass and tp_pass and st_pass

            # Status description
            if overall_pass:
                status_text = "PASS"
            else:
                reasons = []
                if not lufs_pass:
                    diff_sign = "+" if lufs_delta > 0 else ""
                    reasons.append(f"LUFS {diff_sign}{lufs_delta} LU")
                if not tp_pass:
                    reasons.append(f"TP {measured_tp} > {target_tp}")
                if not st_pass:
                    reasons.append(f"ST {measured_st} > {target_st}")
                status_text = f"FAIL ({', '.join(reasons)})"

            results[std["id"]] = ComplianceItem(
                standard_name=std["name"],
                target_lufs=target_lufs,
                tolerance_lu=tolerance,
                measured_lufs=measured_lufs,
                lufs_delta=lufs_delta,
                lufs_pass=lufs_pass,
                target_tp=target_tp,
                measured_tp=measured_tp,
                tp_pass=tp_pass,
                target_short_term=target_st,
                measured_short_term=measured_st,
                short_term_pass=st_pass,
                overall_pass=overall_pass,
                status_text=status_text,
                notes=std["notes"],
            )

        return results


def linear_to_db(val: float, floor_db: float = -120.0) -> float:
    """Convert linear amplitude ratio to decibels."""
    if val <= 1e-6:
        return floor_db
    return 20.0 * math.log10(val)
