"""AudioScope Tags, Broadcast Metadata & Embedded Artwork Viewer.

Displays standard tags, Broadcast Wave (BEXT), iXML production metadata,
CART chunk details, embedded artwork preview with export option, and filterable
raw tag table.
"""

from __future__ import annotations

import io
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.metadata import EmbeddedArtwork, FileMetadata


class MetadataView(QWidget):
    """Exhaustive metadata and broadcast tag viewer."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.metadata: Optional[FileMetadata] = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Splitter: Left (Metadata Tabs) vs Right (Artwork & Summary Card)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Container: Tabs for Standard, BEXT, iXML, CART, Raw Dump
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.meta_tabs = QTabWidget()

        # Tab A: Standard Audio Tags
        self.standard_table = QTableWidget()
        self.standard_table.setColumnCount(2)
        self.standard_table.setHorizontalHeaderLabels(["Tag Name", "Value"])
        self.standard_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.standard_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.standard_table.verticalHeader().setVisible(False)
        self.meta_tabs.addTab(self.standard_table, "Standard Tags")

        # Tab B: Broadcast Wave (BEXT)
        self.bext_widget = QWidget()
        bext_layout = QVBoxLayout(self.bext_widget)
        bext_layout.setContentsMargins(8, 8, 8, 8)
        self.bext_table = QTableWidget()
        self.bext_table.setColumnCount(2)
        self.bext_table.setHorizontalHeaderLabels(["BEXT Field (EBU Tech 3285)", "Value"])
        self.bext_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.bext_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.bext_table.verticalHeader().setVisible(False)
        bext_layout.addWidget(self.bext_table)
        self.meta_tabs.addTab(self.bext_widget, "Broadcast Wave (BEXT)")

        # Tab C: iXML Production Metadata
        self.ixml_widget = QWidget()
        ixml_layout = QVBoxLayout(self.ixml_widget)
        ixml_layout.setContentsMargins(8, 8, 8, 8)
        self.ixml_tree = QTreeWidget()
        self.ixml_tree.setHeaderLabels(["Field / Property", "Value"])
        self.ixml_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.ixml_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ixml_layout.addWidget(self.ixml_tree)
        self.meta_tabs.addTab(self.ixml_widget, "iXML Chunk")

        # Tab D: CART Chunk (AES46-2002)
        self.cart_widget = QWidget()
        cart_layout = QVBoxLayout(self.cart_widget)
        cart_layout.setContentsMargins(8, 8, 8, 8)
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(2)
        self.cart_table.setHorizontalHeaderLabels(["CART Field (AES46-2002)", "Value"])
        self.cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cart_table.verticalHeader().setVisible(False)
        cart_layout.addWidget(self.cart_table)
        self.meta_tabs.addTab(self.cart_widget, "CART (AES46)")

        # Tab E: Raw Tags & Dump
        self.raw_widget = QWidget()
        raw_layout = QVBoxLayout(self.raw_widget)
        raw_layout.setContentsMargins(8, 8, 8, 8)

        raw_search_layout = QHBoxLayout()
        raw_search_label = QLabel("Filter Tags:")
        raw_search_label.setStyleSheet("font-weight: 600; color: #8c93a8;")
        self.raw_search_input = QLineEdit()
        self.raw_search_input.setPlaceholderText("Filter keys or values...")
        self.raw_search_input.textChanged.connect(self._filter_raw_tags)

        copy_btn = QPushButton("Copy All Tags")
        copy_btn.clicked.connect(self._copy_all_raw_tags)

        raw_search_layout.addWidget(raw_search_label)
        raw_search_layout.addWidget(self.raw_search_input)
        raw_search_layout.addWidget(copy_btn)
        raw_layout.addLayout(raw_search_layout)

        self.raw_table = QTableWidget()
        self.raw_table.setColumnCount(2)
        self.raw_table.setHorizontalHeaderLabels(["Raw Key", "Raw Value"])
        self.raw_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.raw_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.raw_table.verticalHeader().setVisible(False)
        raw_layout.addWidget(self.raw_table)
        self.meta_tabs.addTab(self.raw_widget, "Raw Tag Dump")

        left_layout.addWidget(self.meta_tabs)
        splitter.addWidget(left_widget)

        # Right Container: Embedded Artwork Card
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        art_group = QGroupBox("Embedded Album Artwork")
        art_group.setStyleSheet("QGroupBox { font-weight: 700; color: #00d2ff; }")
        art_layout = QVBoxLayout(art_group)
        art_layout.setContentsMargins(16, 20, 16, 16)
        art_layout.setSpacing(12)
        art_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Image Display Area
        self.art_label = QLabel("No Embedded Artwork")
        self.art_label.setFixedSize(260, 260)
        self.art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_label.setStyleSheet(
            "background-color: #12141c; border: 2px dashed #2d3446; border-radius: 8px; color: #6e768e; font-weight: 600;"
        )
        art_layout.addWidget(self.art_label)

        # Details Table
        self.art_info_label = QLabel("No image data detected.")
        self.art_info_label.setStyleSheet("color: #9aa1b8; font-size: 12px;")
        self.art_info_label.setWordWrap(True)
        art_layout.addWidget(self.art_info_label)

        # Export Artwork Button
        self.export_art_btn = QPushButton("Export Artwork...")
        self.export_art_btn.setEnabled(False)
        self.export_art_btn.clicked.connect(self._export_artwork)
        art_layout.addWidget(self.export_art_btn)

        art_layout.addStretch()
        right_layout.addWidget(art_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([700, 320])
        main_layout.addWidget(splitter)

    def load_metadata(self, metadata: FileMetadata) -> None:
        """Display metadata across all tabs and preview embedded artwork."""
        self.metadata = metadata

        # 1. Standard Tags
        standard_items = [
            ("Title", metadata.title),
            ("Artist", metadata.artist),
            ("Album", metadata.album),
            ("Album Artist", metadata.album_artist),
            ("Date / Year", metadata.date),
            ("Genre", metadata.genre),
            ("Track Number", metadata.track_number),
            ("Disc Number", metadata.disc_number),
            ("Composer", metadata.composer),
            ("Publisher / Label", metadata.publisher),
            ("ISRC", metadata.isrc),
            ("BPM / Tempo", metadata.bpm),
            ("Copyright", metadata.copyright),
            ("Comment", metadata.comment),
            ("Encoder", metadata.encoder),
        ]
        self._populate_table(self.standard_table, standard_items)

        # 2. BEXT Chunk
        bext_items = []
        if metadata.bext is not None:
            b = metadata.bext
            bext_items = [
                ("Description", b.description),
                ("Originator", b.originator),
                ("Originator Reference", b.originator_reference),
                ("Origination Date", b.origination_date),
                ("Origination Time", b.origination_time),
                ("Timecode Anchor (Start)", b.timecode_start),
                ("Time Reference (Samples)", f"{b.time_reference:,}"),
                ("BEXT Version", str(b.version)),
                ("SMPTE UMID", b.umid or "None"),
                ("Stored Integrated Loudness", f"{b.loudness_value_lufs} LUFS" if b.loudness_value_lufs is not None else "Not stored"),
                ("Stored Loudness Range (LRA)", f"{b.loudness_range_lu} LU" if b.loudness_range_lu is not None else "Not stored"),
                ("Stored Max True Peak", f"{b.max_true_peak_dbtp} dBTP" if b.max_true_peak_dbtp is not None else "Not stored"),
                ("Coding History", b.coding_history or "None"),
            ]
        self._populate_table(self.bext_table, bext_items)

        # 3. iXML Chunk
        self.ixml_tree.clear()
        if metadata.ixml is not None:
            x = metadata.ixml
            self._add_tree_item(self.ixml_tree, "Project", x.project)
            self._add_tree_item(self.ixml_tree, "Scene", x.scene)
            self._add_tree_item(self.ixml_tree, "Take", x.take)
            self._add_tree_item(self.ixml_tree, "Tape / Roll", x.tape)
            self._add_tree_item(self.ixml_tree, "Circled Take", "YES" if x.circled else "NO")
            self._add_tree_item(self.ixml_tree, "Notes", x.notes)
            self._add_tree_item(self.ixml_tree, "Timecode Rate", x.timecode_rate)
            self._add_tree_item(self.ixml_tree, "Timecode Drop Frame Flag", x.timecode_flag)
            self._add_tree_item(self.ixml_tree, "File Sample Rate", x.file_sample_rate)
            self._add_tree_item(self.ixml_tree, "Audio Bit Depth", x.audio_bit_depth)
            self._add_tree_item(self.ixml_tree, "Family UID", x.family_uid)

            if x.tracks:
                trk_root = QTreeWidgetItem(self.ixml_tree)
                trk_root.setText(0, f"Track List ({len(x.tracks)} tracks)")
                for trk in x.tracks:
                    item = QTreeWidgetItem(trk_root)
                    item.setText(0, f"Track {trk.channel_index} ({trk.name or 'Unnamed'})")
                    item.setText(1, f"Function: {trk.function or 'N/A'}, Interleave: {trk.interleave_index}")
                trk_root.setExpanded(True)

            self.ixml_tree.expandAll()

        # 4. CART Chunk
        cart_items = []
        if metadata.cart is not None:
            c = metadata.cart
            cart_items = [
                ("Version", c.version),
                ("Title", c.title),
                ("Artist", c.artist),
                ("Cut ID", c.cut_id),
                ("Client ID", c.client_id),
                ("Category", c.category),
                ("Classification", c.classification),
                ("Out Cue", c.out_cue),
                ("Start Date / Time", f"{c.start_date} {c.start_time}".strip()),
                ("End Date / Time", f"{c.end_date} {c.end_time}".strip()),
                ("Producer Application", f"{c.producer_app_id} {c.producer_app_version}".strip()),
                ("User Defined", c.user_def),
                ("URL", c.url),
            ]
        self._populate_table(self.cart_table, cart_items)

        # 5. Raw Tag Dump
        self._populate_raw_tags()

        # 6. Embedded Artwork
        if metadata.artwork is not None and metadata.artwork.raw_data:
            art = metadata.artwork
            pixmap = QPixmap()
            if pixmap.loadFromData(art.raw_data):
                scaled = pixmap.scaled(
                    260, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.art_label.setPixmap(scaled)
                self.art_info_label.setText(
                    f"Format: {art.mime_type.upper()}\n"
                    f"Dimensions: {art.dimensions_str}\n"
                    f"Size: {art.formatted_size}\n"
                    f"Type: {art.picture_type}"
                )
                self.export_art_btn.setEnabled(True)
            else:
                self._reset_artwork_ui("Corrupt Image Data")
        else:
            self._reset_artwork_ui("No Embedded Artwork")

    def _reset_artwork_ui(self, message: str) -> None:
        self.art_label.clear()
        self.art_label.setText(message)
        self.art_info_label.setText("No embedded image stream found in this file.")
        self.export_art_btn.setEnabled(False)

    def _populate_table(self, table: QTableWidget, items: list[tuple[str, str]]) -> None:
        table.setRowCount(len(items))
        for row, (k, v) in enumerate(items):
            key_item = QTableWidgetItem(k)
            key_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            key_item.setForeground(QColor(140, 147, 168))

            val_item = QTableWidgetItem(v if v else "—")
            val_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if not v:
                val_item.setForeground(QColor(85, 91, 110))
            table.setItem(row, 0, key_item)
            table.setItem(row, 1, val_item)

    def _add_tree_item(self, tree: QTreeWidget, key: str, value: str) -> None:
        item = QTreeWidgetItem(tree)
        item.setText(0, key)
        item.setText(1, value if value else "—")
        item.setForeground(0, QColor(140, 147, 168))
        if not value:
            item.setForeground(1, QColor(85, 91, 110))

    def _populate_raw_tags(self) -> None:
        if self.metadata is None:
            self.raw_table.setRowCount(0)
            return

        filter_txt = self.raw_search_input.text().strip().lower()
        items = [
            (k, v)
            for k, v in self.metadata.raw_tags.items()
            if not filter_txt or filter_txt in k.lower() or filter_txt in v.lower()
        ]
        self._populate_table(self.raw_table, items)

    def _filter_raw_tags(self) -> None:
        self._populate_raw_tags()

    def _copy_all_raw_tags(self) -> None:
        if self.metadata is None or not self.metadata.raw_tags:
            return
        lines = [f"{k} = {v}" for k, v in self.metadata.raw_tags.items()]
        dump_txt = "\n".join(lines)
        QApplication.clipboard().setText(dump_txt)
        QMessageBox.information(self, "Copied", f"Copied {len(lines)} raw tags to clipboard.")

    def _export_artwork(self) -> None:
        if self.metadata is None or self.metadata.artwork is None or not self.metadata.artwork.raw_data:
            return

        art = self.metadata.artwork
        ext = ".png" if "png" in art.mime_type.lower() else ".jpg"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Embedded Artwork", f"artwork{ext}", f"Images (*{ext} *.png *.jpg *.jpeg)"
        )
        if save_path:
            with open(save_path, "wb") as f:
                f.write(art.raw_data)
            QMessageBox.information(self, "Export Complete", f"Saved artwork to {save_path}")
