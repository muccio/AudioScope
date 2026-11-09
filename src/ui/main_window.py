"""AudioScope MainWindow Shell & Background Worker.

Integrates drag-and-drop handling, multi-threaded background DSP processing,
global header with quick summary badges, tabbed views, and report generation
(JSON, Markdown, Plain Text).
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.analyzer import AudioAnalyzer, AudioMetrics
from src.core.decoder import StreamInfo, UniversalAudioDecoder
from src.core.metadata import FileMetadata, MetadataEngine
from src.ui.hex_widget import HexWidget
from src.ui.loudness_view import LoudnessView
from src.ui.metadata_view import MetadataView
from src.ui.styles import DARK_THEME_QSS


class AnalysisWorker(QThread):
    """Background worker thread for audio decoding, metadata extraction, and DSP analysis."""

    progress = Signal(float, str)  # (fraction 0.0 - 1.0, status message)
    finished = Signal(object, object, object)  # (StreamInfo, AudioMetrics, FileMetadata)
    error = Signal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self._is_canceled = False

    def cancel(self) -> None:
        self._is_canceled = True

    def run(self) -> None:
        try:
            self.progress.emit(0.02, "Inspecting audio stream...")
            stream_info = UniversalAudioDecoder.inspect(self.file_path)

            self.progress.emit(0.08, "Extracting broadcast metadata and chunks...")
            metadata = MetadataEngine.extract(self.file_path, sample_rate=stream_info.sample_rate)

            self.progress.emit(0.15, "Decoding audio stream...")
            audio_data, sample_rate, updated_info = UniversalAudioDecoder.decode_audio_array(
                self.file_path,
                progress_callback=lambda pct, msg: self.progress.emit(pct, msg),
                cancel_check=lambda: self._is_canceled,
            )

            self.progress.emit(0.65, "Computing ITU-R BS.1770-4 loudness and 4x True Peak...")
            metrics = AudioAnalyzer.analyze(
                audio_data,
                sample_rate,
                progress_callback=lambda pct, msg: self.progress.emit(pct, msg),
                cancel_check=lambda: self._is_canceled,
            )

            if not self._is_canceled:
                self.finished.emit(updated_info, metrics, metadata)

        except InterruptedError:
            pass
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """AudioScope Desktop Application MainWindow."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AudioScope — Universal Audio File Inspector & Broadcast Loudness Analyzer")
        self.resize(1340, 880)
        self.setMinimumSize(1080, 680)
        self.setAcceptDrops(True)

        self.current_file_path: Optional[str] = None
        self.current_stream_info: Optional[StreamInfo] = None
        self.current_metrics: Optional[AudioMetrics] = None
        self.current_metadata: Optional[FileMetadata] = None
        self.worker: Optional[AnalysisWorker] = None

        self._init_ui()
        self.setStyleSheet(DARK_THEME_QSS)

    def _init_ui(self) -> None:
        central_widget = QWidget()
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Global Header Bar
        header_frame = QFrame()
        header_frame.setObjectName("GlobalHeader")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)

        # Top row: Brand & Action Buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        title_lbl = QLabel("AudioScope")
        title_lbl.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #00d2ff; letter-spacing: 0.5px;"
        )
        subtitle_lbl = QLabel("Forensic Audio Inspector & Broadcast Loudness Suite")
        subtitle_lbl.setStyleSheet("font-size: 12px; color: #78829c; font-weight: 500;")

        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)
        brand_layout.addWidget(title_lbl)
        brand_layout.addWidget(subtitle_lbl)
        top_row.addLayout(brand_layout)

        top_row.addStretch()

        # Open File Button
        self.open_btn = QPushButton("Open Audio File...")
        self.open_btn.setObjectName("PrimaryButton")
        self.open_btn.clicked.connect(self._on_open_file_dialog)
        top_row.addWidget(self.open_btn)

        # Export Report Dropdown Menu
        self.export_btn = QPushButton("Export Report ▾")
        self.export_btn.setEnabled(False)
        export_menu = QMenu(self)
        export_menu.addAction("Export JSON Report (.json)", lambda: self._export_report("json"))
        export_menu.addAction("Export Markdown Report (.md)", lambda: self._export_report("md"))
        export_menu.addAction("Export Plain Text Log (.txt)", lambda: self._export_report("txt"))
        self.export_btn.setMenu(export_menu)
        top_row.addWidget(self.export_btn)

        header_layout.addLayout(top_row)

        # Bottom row: Drag & Drop Area & Quick Summary Badges
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        # Drag and Drop Landing Strip
        self.drop_area = QFrame()
        self.drop_area.setObjectName("HeaderDropArea")
        drop_layout = QHBoxLayout(self.drop_area)
        drop_layout.setContentsMargins(12, 6, 12, 6)
        self.drop_lbl = QLabel("Drag & Drop Audio File Here (WAV, FLAC, AIFF, MP3, MP4, AAC, OGG, Opus, DSD)")
        self.drop_lbl.setStyleSheet("color: #7b859e; font-weight: 600; font-size: 12px;")
        drop_layout.addWidget(self.drop_lbl)
        bottom_row.addWidget(self.drop_area, stretch=1)

        # Summary Badges Container
        self.badges_layout = QHBoxLayout()
        self.badges_layout.setSpacing(8)

        self.badge_format = QLabel("No File Loaded")
        self.badge_format.setStyleSheet(
            "background-color: #1e2230; color: #8c93a8; border: 1px solid #2d3345; border-radius: 4px; padding: 4px 10px; font-weight: 600;"
        )
        self.badge_lufs = QLabel("— LUFS")
        self.badge_lufs.setStyleSheet(
            "background-color: #1e2230; color: #8c93a8; border: 1px solid #2d3345; border-radius: 4px; padding: 4px 10px; font-weight: 600;"
        )
        self.badge_tp = QLabel("— dBTP")
        self.badge_tp.setStyleSheet(
            "background-color: #1e2230; color: #8c93a8; border: 1px solid #2d3345; border-radius: 4px; padding: 4px 10px; font-weight: 600;"
        )
        self.badge_compliance = QLabel("STANDARDS: —")
        self.badge_compliance.setStyleSheet(
            "background-color: #1e2230; color: #8c93a8; border: 1px solid #2d3345; border-radius: 4px; padding: 4px 10px; font-weight: 700;"
        )

        self.badges_layout.addWidget(self.badge_format)
        self.badges_layout.addWidget(self.badge_lufs)
        self.badges_layout.addWidget(self.badge_tp)
        self.badges_layout.addWidget(self.badge_compliance)
        bottom_row.addLayout(self.badges_layout)

        header_layout.addLayout(bottom_row)
        root_layout.addWidget(header_frame)

        # 2. Main Tabbed Interface
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_loudness = LoudnessView()
        self.tab_metadata = MetadataView()
        self.tab_hex = HexWidget()

        self.tabs.addTab(self.tab_loudness, "Overview & Broadcast Loudness")
        self.tabs.addTab(self.tab_metadata, "Tags & Broadcast Metadata")
        self.tabs.addTab(self.tab_hex, "Hex & Chunk Structure")

        root_layout.addWidget(self.tabs)
        self.setCentralWidget(central_widget)

        # 3. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_msg = QLabel("Ready. Drag an audio file or click 'Open Audio File...' to begin.")
        self.status_msg.setStyleSheet("color: #8c93a8;")
        self.status_bar.addWidget(self.status_msg, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(260)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.speed_benchmark_lbl = QLabel("")
        self.speed_benchmark_lbl.setStyleSheet("color: #00d2ff; font-weight: 600; padding-right: 8px;")
        self.status_bar.addPermanentWidget(self.speed_benchmark_lbl)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_area.setStyleSheet(
                "background-color: #1e2638; border: 2px dashed #00d2ff; border-radius: 8px; padding: 8px 16px;"
            )

    def dragLeaveEvent(self, event) -> None:
        self.drop_area.setStyleSheet(
            "background-color: #1a1e29; border: 2px dashed #343c4f; border-radius: 8px; padding: 8px 16px;"
        )

    def dropEvent(self, event: QDropEvent) -> None:
        self.drop_area.setStyleSheet(
            "background-color: #1a1e29; border: 2px dashed #343c4f; border-radius: 8px; padding: 8px 16px;"
        )
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path):
                self.open_file(file_path)

    def _on_open_file_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Audio File for Inspection & Loudness Analysis",
            "",
            "Audio Files (*.wav *.bwf *.aif *.aiff *.flac *.alac *.mp3 *.ogg *.opus *.m4a *.aac *.wma *.caf *.ac3 *.dsf *.dff);;All Files (*)",
        )
        if file_path:
            self.open_file(file_path)

    def open_file(self, file_path: str) -> None:
        """Start background worker to decode and analyze the specified audio file."""
        if not os.path.isfile(file_path):
            QMessageBox.critical(self, "File Not Found", f"Cannot open: {file_path}")
            return

        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(500)

        self.current_file_path = file_path
        file_name = os.path.basename(file_path)
        self.drop_lbl.setText(f"Active File: {file_name}")

        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_msg.setText(f"Loading {file_name}...")
        self.speed_benchmark_lbl.setText("")
        self.open_btn.setEnabled(False)
        self.export_btn.setEnabled(False)

        # Load hex reader immediately on main thread (it is zero-copy mmap, so instant!)
        try:
            self.tab_hex.load_file(file_path)
        except Exception as e:
            print("Hex reader error:", e)

        # Launch heavy DSP and decoding in background worker
        self.worker = AnalysisWorker(file_path)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _on_worker_progress(self, fraction: float, msg: str) -> None:
        self.progress_bar.setValue(int(fraction * 100))
        self.status_msg.setText(msg)

    def _on_worker_finished(
        self, stream_info: StreamInfo, metrics: AudioMetrics, metadata: FileMetadata
    ) -> None:
        self.current_stream_info = stream_info
        self.current_metrics = metrics
        self.current_metadata = metadata

        self.progress_bar.setVisible(False)
        self.open_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # Update Views
        self.tab_loudness.load_stream_info(stream_info)
        self.tab_loudness.load_metrics(metrics)
        self.tab_metadata.load_metadata(metadata)

        # Update Quick Summary Badges
        self.badge_format.setText(f"{stream_info.container_name.upper()} | {stream_info.codec_name} | {stream_info.sample_rate // 1000}kHz {stream_info.bit_depth}b")
        self.badge_format.setStyleSheet(
            "background-color: #132f4c; color: #00d2ff; border: 1px solid #1e5c8a; border-radius: 4px; padding: 4px 10px; font-weight: 600;"
        )

        self.badge_lufs.setText(f"{metrics.integrated_lufs:.1f} LUFS")
        self.badge_lufs.setStyleSheet(
            "background-color: #1e2230; color: #00e676; border: 1px solid #00b050; border-radius: 4px; padding: 4px 10px; font-weight: 700;"
        )

        tp_col = "#ff3d71" if metrics.true_peak_dbtp > -1.0 else "#00e676"
        self.badge_tp.setText(f"{metrics.true_peak_dbtp:.2f} dBTP")
        self.badge_tp.setStyleSheet(
            f"background-color: #1e2230; color: {tp_col}; border: 1px solid #2d3345; border-radius: 4px; padding: 4px 10px; font-weight: 700;"
        )

        # Overall compliance badge (check EBU R128)
        ebu_comp = metrics.compliance.get("EBU R128")
        if ebu_comp and ebu_comp.overall_pass:
            self.badge_compliance.setText("EBU R128: PASS")
            self.badge_compliance.setStyleSheet(
                "background-color: #004d26; color: #00e676; border: 1px solid #00b050; border-radius: 4px; padding: 4px 10px; font-weight: 700;"
            )
        else:
            self.badge_compliance.setText("EBU R128: FAIL")
            self.badge_compliance.setStyleSheet(
                "background-color: #4a1525; color: #ff3d71; border: 1px solid #d92550; border-radius: 4px; padding: 4px 10px; font-weight: 700;"
            )

        self.status_msg.setText(f"Analysis complete for: {stream_info.file_name}")
        self.speed_benchmark_lbl.setText(
            f"Speed: {metrics.realtime_factor:.1f}x realtime ({metrics.analysis_duration_sec:.2f}s)"
        )

    def _on_worker_error(self, err_msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.open_btn.setEnabled(True)
        self.status_msg.setText(f"Error: {err_msg}")
        QMessageBox.critical(self, "Analysis Error", f"Failed to inspect or analyze audio file:\n\n{err_msg}")

    def _export_report(self, fmt: str) -> None:
        """Export comprehensive forensic and loudness report."""
        if not self.current_stream_info or not self.current_metrics or not self.current_metadata:
            return

        base_name = os.path.splitext(self.current_stream_info.file_name)[0]
        default_file = f"{base_name}_audioscope_report.{fmt}"

        save_path, _ = QFileDialog.getSaveFileName(
            self, f"Export Report as {fmt.upper()}", default_file, f"Reports (*.{fmt})"
        )
        if not save_path:
            return

        s = self.current_stream_info
        m = self.current_metrics
        meta = self.current_metadata

        if fmt == "json":
            report_dict = {
                "file_name": s.file_name,
                "file_path": s.file_path,
                "file_size_bytes": s.file_size_bytes,
                "stream": {
                    "container": s.container_long_name,
                    "codec": s.codec_long_name,
                    "sample_rate_hz": s.sample_rate,
                    "bit_depth": s.bit_depth,
                    "channels": s.channels,
                    "channel_layout": s.channel_layout,
                    "duration_seconds": s.duration_seconds,
                    "duration_samples": s.duration_samples,
                    "timecode_24fps": s.formatted_timecode("24"),
                    "compression_ratio": s.compression_ratio,
                    "is_vbr": s.is_vbr,
                },
                "loudness_and_dynamics": {
                    "integrated_lufs": m.integrated_lufs,
                    "loudness_range_lu": m.loudness_range_lu,
                    "max_short_term_lufs": m.max_short_term_lufs,
                    "max_momentary_lufs": m.max_momentary_lufs,
                    "true_peak_dbtp": m.true_peak_dbtp,
                    "sample_peak_dbfs": m.sample_peak_dbfs,
                    "rms_dbfs": m.rms_dbfs,
                    "crest_factor_db": m.crest_factor_db,
                    "dc_offset_percent": m.dc_offset_percent,
                },
                "compliance_matrix": {
                    k: {
                        "standard": c.standard_name,
                        "target_lufs": c.target_lufs,
                        "measured_lufs": c.measured_lufs,
                        "lufs_pass": c.lufs_pass,
                        "target_tp": c.target_tp,
                        "measured_tp": c.measured_tp,
                        "tp_pass": c.tp_pass,
                        "overall_pass": c.overall_pass,
                        "status": c.status_text,
                    }
                    for k, c in m.compliance.items()
                },
                "metadata": {
                    "title": meta.title,
                    "artist": meta.artist,
                    "album": meta.album,
                    "date": meta.date,
                    "genre": meta.genre,
                    "isrc": meta.isrc,
                },
            }
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2)

        elif fmt == "md":
            md_lines = [
                f"# AudioScope Analysis Report: `{s.file_name}`",
                "",
                "## 1. Stream & Container Specifications",
                f"- **Container:** {s.container_long_name} (`{s.container_name}`)",
                f"- **Codec:** {s.codec_long_name} (`{s.codec_name}`)",
                f"- **Sample Rate:** {s.sample_rate:,} Hz",
                f"- **Bit Depth:** {s.bit_depth}-bit ({s.sample_format})",
                f"- **Channels:** {s.channels} ({s.channel_layout})",
                f"- **Duration:** {s.formatted_duration()} ({s.duration_samples:,} samples)",
                f"- **Timecode (24fps):** `{s.formatted_timecode('24')}`",
                f"- **Compression Ratio:** {s.compression_ratio:.2f}:1",
                "",
                "## 2. Broadcast Loudness & Peak Measurements",
                f"- **Integrated Loudness:** `{m.integrated_lufs:.1f} LUFS`",
                f"- **Loudness Range (LRA):** `{m.loudness_range_lu:.1f} LU`",
                f"- **Max Short-Term (3.0s):** `{m.max_short_term_lufs:.1f} LUFS`",
                f"- **Max Momentary (400ms):** `{m.max_momentary_lufs:.1f} LUFS`",
                f"- **True Peak (4x Oversampled):** `{m.true_peak_dbtp:.2f} dBTP`",
                f"- **Sample Peak:** `{m.sample_peak_dbfs:.2f} dBFS`",
                f"- **RMS Level:** `{m.rms_dbfs:.2f} dBFS`",
                f"- **Crest Factor:** `{m.crest_factor_db:.2f} dB`",
                "",
                "## 3. Standard Compliance Matrix",
                "| Standard | Target LUFS | Measured | Target TP | Measured TP | Status |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
            for c in m.compliance.values():
                status_str = "**PASS**" if c.overall_pass else f"**FAIL** ({c.status_text})"
                md_lines.append(
                    f"| {c.standard_name} | {c.target_lufs:.1f} | {c.measured_lufs:.1f} | {c.target_tp:.1f} dBTP | {c.measured_tp:.2f} dBTP | {status_str} |"
                )

            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines) + "\n")

        else:  # plain text
            txt_lines = [
                f"AudioScope Broadcast Loudness Report: {s.file_name}",
                "=" * 70,
                f"Container:        {s.container_long_name}",
                f"Codec:            {s.codec_long_name}",
                f"Sample Rate:      {s.sample_rate} Hz",
                f"Bit Depth:        {s.bit_depth}-bit",
                f"Channels:         {s.channels} ({s.channel_layout})",
                f"Duration:         {s.formatted_duration()} ({s.duration_samples} samples)",
                f"Timecode:         {s.formatted_timecode('24')} @ 24fps",
                "",
                "LOUDNESS & DYNAMICS (ITU-R BS.1770-4):",
                f"Integrated:       {m.integrated_lufs:.1f} LUFS",
                f"Loudness Range:   {m.loudness_range_lu:.1f} LU",
                f"Max Short-Term:   {m.max_short_term_lufs:.1f} LUFS",
                f"Max Momentary:    {m.max_momentary_lufs:.1f} LUFS",
                f"True Peak (4x):   {m.true_peak_dbtp:.2f} dBTP",
                f"Sample Peak:      {m.sample_peak_dbfs:.2f} dBFS",
                f"RMS Level:        {m.rms_dbfs:.2f} dBFS",
                f"Crest Factor:     {m.crest_factor_db:.2f} dB",
                "",
                "COMPLIANCE MATRIX:",
            ]
            for c in m.compliance.values():
                txt_lines.append(f"  {c.standard_name.ljust(35)}: {'[PASS]' if c.overall_pass else '[FAIL]'} ({c.status_text})")

            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(txt_lines) + "\n")

        QMessageBox.information(self, "Export Complete", f"Report saved successfully to:\n{save_path}")
