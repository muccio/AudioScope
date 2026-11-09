"""AudioScope Broadcast Loudness, Stream Specs & Compliance Matrix Widget.

Displays stream specs, interactive timecode at user-selected frame rates,
high-precision broadcast level meters, and the Standard Compliance Matrix.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QLinearGradient, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.analyzer import AudioMetrics, ComplianceItem
from src.core.decoder import StreamInfo, samples_to_timecode


class BroadcastLevelBar(QWidget):
    """Custom pro audio horizontal meter bar with target indicator and gradient."""

    def __init__(
        self,
        min_val: float = -60.0,
        max_val: float = 0.0,
        target_val: Optional[float] = None,
        unit: str = "LUFS",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.target_val = target_val
        self.unit = unit
        self.current_val: float = min_val
        self.setFixedHeight(26)
        self.setMinimumWidth(160)

    def set_value(self, val: float) -> None:
        self.current_val = val
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(22, 25, 34))
        painter.drawRoundedRect(0, 0, w, h, 4, 4)

        # Clamped normalized fraction
        clamped = max(self.min_val, min(self.max_val, self.current_val))
        span = self.max_val - self.min_val
        frac = (clamped - self.min_val) / span if span > 0 else 0.0
        bar_w = int(w * frac)

        # Meter Gradient: Green (-60 to -18) -> Amber (-18 to -1) -> Red (>-1)
        if bar_w > 0:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor(0, 180, 216))
            grad.setColorAt(0.65, QColor(0, 230, 118))
            grad.setColorAt(0.85, QColor(255, 171, 0))
            grad.setColorAt(1.0, QColor(255, 61, 113))

            painter.setBrush(grad)
            painter.drawRoundedRect(0, 0, bar_w, h, 4, 4)

        # Draw Target Line (e.g. -23 LUFS or -1.0 dBTP)
        if self.target_val is not None and self.min_val <= self.target_val <= self.max_val:
            t_frac = (self.target_val - self.min_val) / span
            t_x = int(w * t_frac)
            painter.setPen(QPen(QColor(255, 255, 255, 200), 2, Qt.PenStyle.DashLine))
            painter.drawLine(t_x, 2, t_x, h - 2)

        # Border
        painter.setPen(QPen(QColor(42, 48, 64), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        # Text readout
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        text = f"{self.current_val:.1f} {self.unit}" if self.current_val > self.min_val else f"— {self.unit}"
        painter.drawText(0, 0, w - 8, h, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)


class LoudnessView(QWidget):
    """Overview & Broadcast Loudness View."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.stream_info: Optional[StreamInfo] = None
        self.metrics: Optional[AudioMetrics] = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(16)

        # Upper Section: Splitter (Left: Stream Specs, Right: Broadcast Loudness Meters)
        upper_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Stream Specifications Card
        specs_box = QGroupBox("Stream & Container Specifications")
        specs_box.setStyleSheet("QGroupBox { font-weight: 700; color: #00d2ff; }")
        specs_layout = QGridLayout(specs_box)
        specs_layout.setContentsMargins(16, 20, 16, 16)
        specs_layout.setSpacing(10)

        self.spec_labels: Dict[str, QLabel] = {}
        spec_keys = [
            ("Container Format", "container"),
            ("Audio Codec", "codec"),
            ("Sample Rate", "sample_rate"),
            ("Bit Depth & Format", "bit_depth"),
            ("Channels & Layout", "channels"),
            ("Bitrate & Mode", "bitrate"),
            ("Duration (Time)", "duration_time"),
            ("Exact Sample Count", "duration_samples"),
            ("File Size & Uncompressed", "file_size"),
            ("Compression Ratio", "compression_ratio"),
        ]

        for row, (label_txt, key) in enumerate(spec_keys):
            name_lbl = QLabel(label_txt + ":")
            name_lbl.setStyleSheet("color: #8c93a8; font-weight: 600;")
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet("color: #f0f4fc; font-weight: 500;")
            val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            specs_layout.addWidget(name_lbl, row, 0)
            specs_layout.addWidget(val_lbl, row, 1)
            self.spec_labels[key] = val_lbl

        # Interactive Timecode selector row
        tc_row = len(spec_keys)
        tc_name_lbl = QLabel("Timecode (SMPTE):")
        tc_name_lbl.setStyleSheet("color: #8c93a8; font-weight: 600;")
        specs_layout.addWidget(tc_name_lbl, tc_row, 0)

        tc_widget = QWidget()
        tc_layout = QHBoxLayout(tc_widget)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(8)

        self.tc_value_lbl = QLabel("00:00:00:00")
        self.tc_value_lbl.setStyleSheet("color: #00e676; font-weight: 700; font-family: monospace; font-size: 13px;")

        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["24", "25", "23.976", "29.97 DF", "29.97 NDF", "30", "50", "59.94", "60"])
        self.fps_combo.currentTextChanged.connect(self._on_fps_changed)

        tc_layout.addWidget(self.tc_value_lbl)
        tc_layout.addWidget(self.fps_combo)
        tc_layout.addStretch()
        specs_layout.addWidget(tc_widget, tc_row, 1)

        upper_splitter.addWidget(specs_box)

        # Right: Broadcast Loudness & Peak Measurements Card
        loudness_box = QGroupBox("Broadcast Loudness & Dynamic Measurements")
        loudness_box.setStyleSheet("QGroupBox { font-weight: 700; color: #00e676; }")
        loudness_layout = QGridLayout(loudness_box)
        loudness_layout.setContentsMargins(16, 20, 16, 16)
        loudness_layout.setSpacing(12)

        # Level Bars
        # 1. Integrated Loudness
        int_lbl = QLabel("Integrated Loudness (LUFS):")
        int_lbl.setStyleSheet("color: #8c93a8; font-weight: 600;")
        self.meter_integrated = BroadcastLevelBar(min_val=-50.0, max_val=-5.0, target_val=-23.0, unit="LUFS")
        loudness_layout.addWidget(int_lbl, 0, 0)
        loudness_layout.addWidget(self.meter_integrated, 0, 1)

        # 2. Max Short-Term Loudness (3s window)
        st_lbl = QLabel("Max Short-Term (3.0s):")
        st_lbl.setStyleSheet("color: #8c93a8; font-weight: 600;")
        self.meter_short_term = BroadcastLevelBar(min_val=-50.0, max_val=-5.0, target_val=-18.0, unit="LUFS")
        loudness_layout.addWidget(st_lbl, 1, 0)
        loudness_layout.addWidget(self.meter_short_term, 1, 1)

        # 3. Max Momentary Loudness (400ms window)
        mom_lbl = QLabel("Max Momentary (400ms):")
        mom_lbl.setStyleSheet("color: #8c93a8; font-weight: 600;")
        self.meter_momentary = BroadcastLevelBar(min_val=-50.0, max_val=-5.0, target_val=-15.0, unit="LUFS")
        loudness_layout.addWidget(mom_lbl, 2, 0)
        loudness_layout.addWidget(self.meter_momentary, 2, 1)

        # 4. True Peak (4x Oversampled)
        tp_lbl = QLabel("Max True Peak (4x TP):")
        tp_lbl.setStyleSheet("color: #8c93a8; font-weight: 600;")
        self.meter_true_peak = BroadcastLevelBar(min_val=-40.0, max_val=6.0, target_val=-1.0, unit="dBTP")
        loudness_layout.addWidget(tp_lbl, 3, 0)
        loudness_layout.addWidget(self.meter_true_peak, 3, 1)

        # Numerical Metric Badges
        num_metrics_widget = QWidget()
        num_layout = QGridLayout(num_metrics_widget)
        num_layout.setContentsMargins(0, 8, 0, 0)
        num_layout.setSpacing(10)

        self.val_lra = QLabel("—")
        self.val_sample_peak = QLabel("—")
        self.val_rms = QLabel("—")
        self.val_crest = QLabel("—")
        self.val_dc = QLabel("—")

        cards = [
            ("Loudness Range (LRA)", self.val_lra, "#00d2ff"),
            ("Sample Peak (Global)", self.val_sample_peak, "#f0f4fc"),
            ("RMS Level (Total)", self.val_rms, "#f0f4fc"),
            ("Crest Factor", self.val_crest, "#ffab00"),
            ("DC Offset (Max)", self.val_dc, "#f0f4fc"),
        ]

        for idx, (title, lbl, col) in enumerate(cards):
            c_frame = QFrame()
            c_frame.setStyleSheet(
                "background-color: #12141c; border: 1px solid #282d3c; border-radius: 6px; padding: 6px;"
            )
            c_lay = QVBoxLayout(c_frame)
            c_lay.setContentsMargins(6, 4, 6, 4)
            c_lay.setSpacing(2)

            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("color: #7b839b; font-size: 11px; font-weight: 600;")
            lbl.setStyleSheet(f"color: {col}; font-size: 14px; font-weight: 700;")

            c_lay.addWidget(t_lbl)
            c_lay.addWidget(lbl)

            row = idx // 3
            col_idx = idx % 3
            num_layout.addWidget(c_frame, row, col_idx)

        loudness_layout.addWidget(num_metrics_widget, 4, 0, 1, 2)
        upper_splitter.addWidget(loudness_box)

        upper_splitter.setSizes([450, 550])
        container_layout.addWidget(upper_splitter)

        # Lower Section: Standard Compliance Matrix Table
        comp_box = QGroupBox("International Broadcast & Streaming Standards Compliance Matrix")
        comp_box.setStyleSheet("QGroupBox { font-weight: 700; color: #ffab00; }")
        comp_layout = QVBoxLayout(comp_box)
        comp_layout.setContentsMargins(16, 20, 16, 16)
        comp_layout.setSpacing(8)

        self.compliance_table = QTableWidget()
        self.compliance_table.setColumnCount(8)
        self.compliance_table.setHorizontalHeaderLabels([
            "Standard / Target",
            "Target LUFS",
            "Measured",
            "Delta (LU)",
            "Target Max TP",
            "Measured TP",
            "Compliance Status",
            "Specification Notes",
        ])
        self.compliance_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.compliance_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.compliance_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.compliance_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.compliance_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.compliance_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.compliance_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.compliance_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.compliance_table.verticalHeader().setVisible(False)
        self.compliance_table.setMinimumHeight(240)

        comp_layout.addWidget(self.compliance_table)
        container_layout.addWidget(comp_box)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def load_stream_info(self, info: StreamInfo) -> None:
        """Update stream specifications card."""
        self.stream_info = info

        self.spec_labels["container"].setText(f"{info.container_long_name} ({info.container_name})")
        profile_str = f" [{info.profile}]" if info.profile else ""
        self.spec_labels["codec"].setText(f"{info.codec_long_name} ({info.codec_name}){profile_str}")
        self.spec_labels["sample_rate"].setText(f"{info.sample_rate:,} Hz ({info.sample_rate / 1000.0:.1f} kHz)")
        self.spec_labels["bit_depth"].setText(f"{info.bit_depth}-bit ({info.sample_format})")
        self.spec_labels["channels"].setText(f"{info.channels} ch ({info.channel_layout})")

        vbr_tag = "VBR (Variable)" if info.is_vbr else "CBR (Constant)"
        calc_kbps = f"{info.calculated_bitrate // 1000:,} kbps (avg)" if info.calculated_bitrate else "—"
        self.spec_labels["bitrate"].setText(f"{calc_kbps} | {vbr_tag}")

        self.spec_labels["duration_time"].setText(f"{info.formatted_duration()} ({info.duration_seconds:.3f} s)")
        self.spec_labels["duration_samples"].setText(f"{info.duration_samples:,} samples")

        file_mb = info.file_size_bytes / (1024.0 * 1024.0)
        uncomp_mb = info.uncompressed_size_bytes / (1024.0 * 1024.0)
        self.spec_labels["file_size"].setText(f"{file_mb:.2f} MB on disk | {uncomp_mb:.2f} MB uncompressed")

        saved_pct = max(0.0, (1.0 - (info.file_size_bytes / float(info.uncompressed_size_bytes)))) * 100.0 if info.uncompressed_size_bytes > 0 else 0.0
        self.spec_labels["compression_ratio"].setText(f"{info.compression_ratio:.2f} : 1 ({saved_pct:.1f}% space saved)")

        # Update initial timecode
        self._update_timecode()

    def _on_fps_changed(self) -> None:
        self._update_timecode()

    def _update_timecode(self) -> None:
        if self.stream_info is not None:
            fps = self.fps_combo.currentText()
            tc = self.stream_info.formatted_timecode(fps)
            self.tc_value_lbl.setText(tc)

    def load_metrics(self, metrics: AudioMetrics) -> None:
        """Update broadcast loudness meters and compliance matrix table."""
        self.metrics = metrics

        # Level Bars
        self.meter_integrated.set_value(metrics.integrated_lufs)
        self.meter_short_term.set_value(metrics.max_short_term_lufs)
        self.meter_momentary.set_value(metrics.max_momentary_lufs)
        self.meter_true_peak.set_value(metrics.true_peak_dbtp)

        # Dynamic Metrics Cards
        self.val_lra.setText(f"{metrics.loudness_range_lu:.1f} LU")
        self.val_sample_peak.setText(f"{metrics.sample_peak_dbfs:.2f} dBFS")
        self.val_rms.setText(f"{metrics.rms_dbfs:.2f} dBFS")
        self.val_crest.setText(f"{metrics.crest_factor_db:.2f} dB")

        max_dc = max(metrics.dc_offset_percent) if metrics.dc_offset_percent else 0.0
        self.val_dc.setText(f"{max_dc:.4f}%")

        # Compliance Table
        self.compliance_table.setRowCount(len(metrics.compliance))
        for row, (std_id, item) in enumerate(metrics.compliance.items()):
            # Col 0: Name
            it_name = QTableWidgetItem(item.standard_name)
            it_name.setForeground(QColor(226, 230, 240))
            self.compliance_table.setItem(row, 0, it_name)

            # Col 1: Target LUFS
            it_tgt = QTableWidgetItem(f"{item.target_lufs:.1f} LUFS (±{item.tolerance_lu:.1f})")
            it_tgt.setForeground(QColor(140, 147, 168))
            self.compliance_table.setItem(row, 1, it_tgt)

            # Col 2: Measured LUFS
            it_meas = QTableWidgetItem(f"{item.measured_lufs:.1f} LUFS")
            it_meas.setForeground(QColor(0, 230, 118) if item.lufs_pass else QColor(255, 61, 113))
            self.compliance_table.setItem(row, 2, it_meas)

            # Col 3: Delta
            sign = "+" if item.lufs_delta > 0 else ""
            it_delta = QTableWidgetItem(f"{sign}{item.lufs_delta:.1f} LU")
            it_delta.setForeground(QColor(0, 230, 118) if item.lufs_pass else QColor(255, 171, 0))
            self.compliance_table.setItem(row, 3, it_delta)

            # Col 4: Target Max TP
            it_ttp = QTableWidgetItem(f"{item.target_tp:.1f} dBTP")
            it_ttp.setForeground(QColor(140, 147, 168))
            self.compliance_table.setItem(row, 4, it_ttp)

            # Col 5: Measured TP
            it_mtp = QTableWidgetItem(f"{item.measured_tp:.2f} dBTP")
            it_mtp.setForeground(QColor(0, 230, 118) if item.tp_pass else QColor(255, 61, 113))
            self.compliance_table.setItem(row, 5, it_mtp)

            # Col 6: Status
            it_status = QTableWidgetItem("PASS" if item.overall_pass else "FAIL")
            it_status.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            if item.overall_pass:
                it_status.setForeground(QColor(0, 230, 118))
                it_status.setBackground(QColor(0, 77, 38))
            else:
                it_status.setForeground(QColor(255, 61, 113))
                it_status.setBackground(QColor(74, 21, 37))
            self.compliance_table.setItem(row, 6, it_status)

            # Col 7: Notes
            it_notes = QTableWidgetItem(item.notes)
            it_notes.setForeground(QColor(120, 128, 148))
            self.compliance_table.setItem(row, 7, it_notes)
