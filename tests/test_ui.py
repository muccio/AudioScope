"""UI Integration and Offscreen Rendering Tests."""

import json
import os
import tempfile
import numpy as np
import scipy.io.wavfile as wav

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.core.decoder import UniversalAudioDecoder
from src.core.analyzer import AudioAnalyzer
from src.core.metadata import MetadataEngine
from src.ui.main_window import MainWindow
from src.ui.hex_widget import HexWidget


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_init_and_load(qapp):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        sr = 48000
        t = np.linspace(0, 0.5, sr // 2, endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        wav.write(tmp_path, sr, audio)

        window = MainWindow()
        window.show()

        # Load file directly
        stream_info = UniversalAudioDecoder.inspect(tmp_path)
        audio_data, _, _ = UniversalAudioDecoder.decode_audio_array(tmp_path)
        metrics = AudioAnalyzer.analyze(audio_data, sr)
        metadata = MetadataEngine.extract(tmp_path, sr)

        # Simulate worker finish
        window._on_worker_finished(stream_info, metrics, metadata)

        # Verify badges and views populated
        assert window.badge_format.text() != "No File Loaded"
        assert "LUFS" in window.badge_lufs.text()
        assert "dBTP" in window.badge_tp.text()

        # Switch tabs
        window.tabs.setCurrentIndex(0)
        assert window.tabs.currentIndex() == 0
        window.tabs.setCurrentIndex(1)
        assert window.tabs.currentIndex() == 1
        window.tabs.setCurrentIndex(2)
        assert window.tabs.currentIndex() == 2

        # Test HexWidget search & jump
        hex_tab = window.tab_hex
        hex_tab.load_file(tmp_path)
        assert hex_tab.hex_model.rowCount() > 0

        # Jump to offset
        hex_tab.jump_input.setText("0x0000000C")
        hex_tab._on_jump_offset()
        assert "Jumped to offset" in hex_tab.search_status.text()

        # Search pattern
        hex_tab.search_input.setText("fmt")
        hex_tab._on_find_next()
        assert "Match found" in hex_tab.search_status.text()

        if hex_tab.reader is not None:
            hex_tab.reader.close()
            hex_tab.reader = None

        window.close()

    finally:
        if "hex_tab" in locals() and hex_tab.reader is not None:
            hex_tab.reader.close()
            hex_tab.reader = None
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
