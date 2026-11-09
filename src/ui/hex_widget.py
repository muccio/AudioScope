"""AudioScope Virtualized Hex Viewer & Container Chunk Inspector Widget.

Backed by QAbstractTableModel and memory-mapped HexReader for zero-copy
exploration of multi-gigabyte files with synchronized container chunk hierarchy.
"""

from __future__ import annotations

import re
from typing import List, Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.hex_reader import ChunkNode, ContainerChunkParser, HexReader


class VirtualHexTableModel(QAbstractTableModel):
    """Virtual table model requesting 16-byte rows lazily from memory-mapped file."""

    COLUMNS = ["Offset (Hex)", "Hex Bytes (00-0F)", "ASCII Dump"]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.reader: Optional[HexReader] = None
        self._highlight_range: Optional[Tuple[int, int]] = None  # (start_offset, end_offset)

    def set_reader(self, reader: Optional[HexReader]) -> None:
        self.beginResetModel()
        self.reader = reader
        self._highlight_range = None
        self.endResetModel()

    def set_highlight_range(self, start_offset: int, end_offset: int) -> None:
        """Highlight a specific chunk offset range."""
        self._highlight_range = (start_offset, end_offset)
        # Notify visible views to redraw
        self.layoutChanged.emit()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self.reader is None or parent.isValid():
            return 0
        return self.reader.total_rows

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 3

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.reader is None:
            return None

        row = index.row()
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            offset, raw, hex_str, ascii_str = self.reader.get_row_data(row)
            if col == 0:
                return f"{offset:08X}"
            elif col == 1:
                return hex_str
            elif col == 2:
                return ascii_str

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        elif role == Qt.ItemDataRole.BackgroundRole:
            if self._highlight_range is not None:
                row_start = row * 16
                row_end = row_start + 16
                hl_start, hl_end = self._highlight_range
                if max(row_start, hl_start) < min(row_end, hl_end):
                    return QColor(24, 60, 92)  # Highlighting color

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return QColor(100, 181, 246)  # Light blue offset
            elif col == 1:
                return QColor(226, 230, 240)  # Hex bytes
            elif col == 2:
                return QColor(0, 230, 118)   # Neon green ASCII dump

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        return None


class HexWidget(QWidget):
    """Integrated container chunk tree and virtualized hex editor."""

    chunk_selected = Signal(int, int)  # (start_offset, end_offset)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.reader: Optional[HexReader] = None
        self.current_file: str = ""
        self.last_search_offset: int = 0
        self.last_search_pattern: bytes = b""

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Top Control & Search Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Jump to Offset controls
        jump_label = QLabel("Jump to Offset:")
        jump_label.setStyleSheet("font-weight: 600; color: #8c93a8;")
        self.jump_input = QLineEdit()
        self.jump_input.setPlaceholderText("Hex (0x1A40 or 1A40) or Dec (6720)")
        self.jump_input.setFixedWidth(240)
        self.jump_input.returnPressed.connect(self._on_jump_offset)

        jump_btn = QPushButton("Go")
        jump_btn.setFixedWidth(50)
        jump_btn.clicked.connect(self._on_jump_offset)

        toolbar.addWidget(jump_label)
        toolbar.addWidget(self.jump_input)
        toolbar.addWidget(jump_btn)

        toolbar.addSpacing(20)

        # Search Pattern controls
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-weight: 600; color: #8c93a8;")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ASCII text (e.g. bext, RIFF) or Hex bytes (e.g. 52 49 46 46)")
        self.search_input.setMinimumWidth(280)
        self.search_input.returnPressed.connect(self._on_find_next)

        find_next_btn = QPushButton("Find Next")
        find_next_btn.clicked.connect(self._on_find_next)

        find_prev_btn = QPushButton("Find Prev")
        find_prev_btn.clicked.connect(self._on_find_prev)

        self.search_status = QLabel("")
        self.search_status.setStyleSheet("color: #00d2ff; font-weight: 500;")

        toolbar.addWidget(search_label)
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(find_next_btn)
        toolbar.addWidget(find_prev_btn)
        toolbar.addWidget(self.search_status)
        toolbar.addStretch()

        main_layout.addLayout(toolbar)

        # Main Splitter (Left: Chunk Tree, Right: Virtual Hex Table)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Container Chunk Tree
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        tree_header = QLabel("Container Chunk & Box Hierarchy")
        tree_header.setStyleSheet("font-size: 14px; font-weight: 700; color: #00d2ff;")
        left_layout.addWidget(tree_header)

        self.chunk_tree = QTreeWidget()
        self.chunk_tree.setHeaderLabels(["Chunk / Atom", "Offset", "Size", "Description"])
        self.chunk_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.chunk_tree.itemClicked.connect(self._on_chunk_item_clicked)
        left_layout.addWidget(self.chunk_tree)

        splitter.addWidget(left_widget)

        # Right: Virtual Hex Table
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        hex_header = QLabel("Memory-Mapped Zero-Copy Hex Viewer")
        hex_header.setStyleSheet("font-size: 14px; font-weight: 700; color: #00e676;")
        right_layout.addWidget(hex_header)

        self.hex_model = VirtualHexTableModel(self)
        self.hex_table = QTableView()
        self.hex_table.setModel(self.hex_model)

        # Monospace font for exact hex alignment
        mono_font = QFont("DejaVu Sans Mono", 10)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.hex_table.setFont(mono_font)

        self.hex_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.hex_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.hex_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.hex_table.setColumnWidth(0, 110)
        self.hex_table.setColumnWidth(1, 410)
        self.hex_table.verticalHeader().setDefaultSectionSize(22)
        self.hex_table.verticalHeader().setVisible(False)
        self.hex_table.setShowGrid(False)

        right_layout.addWidget(self.hex_table)
        splitter.addWidget(right_widget)

        # Set 35% / 65% splitter ratio
        splitter.setSizes([380, 720])
        main_layout.addWidget(splitter)

    def load_file(self, file_path: str) -> None:
        """Load file into virtual hex reader and chunk tree."""
        self.current_file = file_path
        if self.reader is not None:
            self.reader.close()

        self.reader = HexReader(file_path)
        self.hex_model.set_reader(self.reader)
        self.last_search_offset = 0
        self.last_search_pattern = b""
        self.search_status.setText("")

        # Parse container chunks
        chunks = ContainerChunkParser.parse(file_path)
        self._populate_chunk_tree(chunks)

        # Select first row
        if self.reader.total_rows > 0:
            self.scroll_to_offset(0)

    def _populate_chunk_tree(self, chunks: List[ChunkNode]) -> None:
        """Populate hierarchical chunk tree widget."""
        self.chunk_tree.clear()

        def add_node(parent_item, node: ChunkNode):
            item = QTreeWidgetItem(parent_item)
            item.setText(0, node.name)
            item.setText(1, node.offset_hex)
            item.setText(2, node.length_formatted)
            item.setText(3, node.description)
            item.setData(0, Qt.ItemDataRole.UserRole, (node.offset_start, node.offset_end))

            for child in node.children:
                add_node(item, child)

        for chunk in chunks:
            add_node(self.chunk_tree, chunk)

        self.chunk_tree.expandAll()

    def _on_chunk_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle chunk tree click: jump and highlight hex viewer."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            start_off, end_off = data
            self.scroll_to_offset(start_off)
            self.hex_model.set_highlight_range(start_off, end_off)
            self.chunk_selected.emit(start_off, end_off)

    def scroll_to_offset(self, offset: int) -> None:
        """Scroll virtual hex table to specific byte offset and select row."""
        if self.reader is None or self.reader.total_rows == 0:
            return

        row = max(0, min(self.reader.total_rows - 1, offset // 16))
        idx = self.hex_model.index(row, 1)
        self.hex_table.scrollTo(idx, QTableView.ScrollHint.PositionAtCenter)
        self.hex_table.selectRow(row)

    def _on_jump_offset(self) -> None:
        """Process Jump to Offset input."""
        txt = self.jump_input.text().strip()
        if not txt:
            return

        try:
            if txt.lower().startswith("0x"):
                offset = int(txt, 16)
            elif any(c in "abcdefABCDEF" for c in txt):
                offset = int(txt, 16)
            else:
                offset = int(txt)
        except ValueError:
            QMessageBox.warning(self, "Invalid Offset", f"Cannot parse '{txt}' as hexadecimal or decimal offset.")
            return

        if self.reader and (offset < 0 or offset >= self.reader.file_size):
            QMessageBox.warning(
                self,
                "Offset Out of Bounds",
                f"Offset 0x{offset:X} ({offset}) exceeds file size ({self.reader.file_size} bytes)."
            )
            return

        self.scroll_to_offset(offset)
        self.search_status.setText(f"Jumped to offset 0x{offset:08X} ({offset:,} bytes)")

    def _get_search_pattern(self) -> bytes:
        """Extract bytes to search from user input (ASCII string or hex tokens)."""
        txt = self.search_input.text().strip()
        if not txt:
            return b""

        # Check if user typed hex tokens like "52 49 46 46" or "52494646"
        clean_hex = txt.replace(" ", "").replace("0x", "")
        if len(clean_hex) >= 2 and len(clean_hex) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in clean_hex):
            try:
                return bytes.fromhex(clean_hex)
            except Exception:
                pass

        # Default to raw ASCII text
        return txt.encode("latin-1", errors="replace")

    def _on_find_next(self) -> None:
        """Search forward for pattern."""
        if self.reader is None:
            return

        pattern = self._get_search_pattern()
        if not pattern:
            return

        start_pos = self.last_search_offset + 1 if pattern == self.last_search_pattern else 0
        match_pos = self.reader.search_pattern(pattern, start_pos)

        if match_pos >= 0:
            self.last_search_offset = match_pos
            self.last_search_pattern = pattern
            self.scroll_to_offset(match_pos)
            self.hex_model.set_highlight_range(match_pos, match_pos + len(pattern))
            self.search_status.setText(f"Match found at 0x{match_pos:08X} ({match_pos:,})")
        else:
            if start_pos > 0:
                # Wrap search from start
                match_pos = self.reader.search_pattern(pattern, 0)
                if match_pos >= 0:
                    self.last_search_offset = match_pos
                    self.last_search_pattern = pattern
                    self.scroll_to_offset(match_pos)
                    self.hex_model.set_highlight_range(match_pos, match_pos + len(pattern))
                    self.search_status.setText(f"Wrapped: Match found at 0x{match_pos:08X}")
                    return
            self.search_status.setText("Pattern not found.")

    def _on_find_prev(self) -> None:
        """Search backward for pattern."""
        if self.reader is None:
            return

        pattern = self._get_search_pattern()
        if not pattern:
            return

        start_pos = max(0, self.last_search_offset - 1)
        match_pos = self.reader.search_pattern_reverse(pattern, start_pos)

        if match_pos >= 0:
            self.last_search_offset = match_pos
            self.last_search_pattern = pattern
            self.scroll_to_offset(match_pos)
            self.hex_model.set_highlight_range(match_pos, match_pos + len(pattern))
            self.search_status.setText(f"Match found at 0x{match_pos:08X}")
        else:
            self.search_status.setText("Previous match not found.")

    def closeEvent(self, event) -> None:
        if self.reader is not None:
            self.reader.close()
            self.reader = None
        super().closeEvent(event)
