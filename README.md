# AudioScope: Universal Audio File Inspector & Broadcast Loudness Analyzer

<p align="center">
  <strong>Production-Grade Forensic Audio Analysis & ITU-R BS.1770-4 Compliance Suite</strong><br>
  <em>Standalone Native Desktop Application for macOS & Windows</em>
</p>

---

## 1. Overview

**AudioScope** is a high-performance, cross-platform desktop application designed for audio engineers, mastering facilities, broadcast compliance quality-assurance teams, and forensic analysts. It combines low-level binary inspection (memory-mapped virtualized hex viewer with container chunk parsing) with broadcast-standard loudness and dynamics measurement (dual-gated integrated LUFS, 4x oversampled True Peak dBTP, EBU Tech 3342 Loudness Range, short-term and momentary sliding windows).

### Key Features
- **Universal Container Demuxing & Decoding (PyAV / FFmpeg):**
  Demuxes and decodes arbitrary digital audio formats: Broadcast WAV (BWF), RF64, AIFF, FLAC, ALAC, MP3, OGG, Opus, AAC / M4A, WMA, CAF, AC3, and DSD/DSF.
- **Virtualized Zero-Copy Hex Viewer (`mmap`):**
  Instantaneous scrolling and exploration of multi-gigabyte files with virtually zero RAM footprint. Includes byte pattern / ASCII search and jump-to-offset navigation.
- **Hierarchical Container Chunk Parser:**
  Interactive structural tree for RIFF (`fmt `, `bext`, `iXML`, `cart`, `data`), AIFF (`COMM`, `SSND`), MP3 (`ID3v2`, frame sync words, `Xing`/`Info`/`LAME`), FLAC (`STREAMINFO`, `VORBIS_COMMENT`, `PICTURE`), and MP4/M4A box hierarchies (`ftyp`, `moov`, `trak`, `mdia`, `stbl`, `mdat`). Selecting any chunk synchronizes with and highlights the hex viewer.
- **Exhaustive Broadcast Metadata Engine:**
  - Standard ID3 / Vorbis / MP4 / APE tags.
  - **Broadcast Wave (BEXT)** EBU Tech 3285 (TimeReference sample count to timecode, originator, loudness values, coding history).
  - **iXML Production Metadata** (Project, Scene, Take, Tape, Circled, Track lists, recorder specifications).
  - **CART Chunk** (AES46-2002 radio automation).
  - **Embedded Artwork Extraction** (dimensions, format, preview, and image export).
  - Filterable raw tag dump and clipboard export.
- **ITU-R BS.1770-4 / EBU R128 Broadcast DSP Analyzer:**
  - Integrated Loudness (LUFS / LKFS) with absolute (-70 LUFS) and relative (-10 LU) gating.
  - Loudness Range (LRA) per EBU Tech 3342.
  - Max Short-Term Loudness (3.0-second sliding window).
  - Max Momentary Loudness (400 ms sliding window).
  - 4x Polyphase Oversampled True Peak (dBTP) per ITU-R BS.1770-4 Annex 2.
  - Sample Peak (dBFS), RMS (dBFS), Crest Factor (dB), and DC Offset percentage.
  - Real-time International Standards Compliance Matrix (EBU R128, ATSC A/85 CALM Act, Spotify, Apple Music, Netflix, Amazon Music, Tidal).
- **Pro Audio Dark Mode UI (PySide6 / Qt 6):**
  High-contrast pro audio console styling with neon cyan/green metering, drag-and-drop file ingestion, and multi-format report exporter (JSON, Markdown, Plain Text).

---

## 2. Project Architecture

```
audioscope/
├── pyproject.toml                  # PEP 517/621 project configuration
├── requirements.txt                # Production dependencies
├── README.md                       # Comprehensive documentation
├── run.py                          # Local development entry point
├── packaging/
│   ├── audioscope.spec             # Master cross-platform PyInstaller specification
│   ├── rthook_qt.py                # Frozen bundle Qt platform plugin runtime hook
│   ├── build_macos.sh              # macOS .app and .dmg automated build pipeline
│   ├── build_windows.ps1           # Windows standalone executable build pipeline
│   ├── installer.iss               # Inno Setup Windows installer compiler script
│   └── assets/
│       ├── icon.png                # High-res raw source graphic
│       ├── icon.ico                # Windows multi-size icon (16x16 to 256x256)
│       └── icon.icns               # macOS multi-resolution icon bundle
└── src/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── decoder.py              # PyAV universal audio stream demuxer & timecode
    │   ├── metadata.py             # Mutagen + BEXT + iXML + CART + Artwork extractor
    │   ├── analyzer.py             # ITU-R BS.1770-4, 4x True Peak, RMS, LRA, Compliance
    │   └── hex_reader.py           # mmap virtualized binary reader & chunk parser
    └── ui/
        ├── __init__.py
        ├── main_window.py          # MainWindow shell, drag-and-drop & worker QThread
        ├── hex_widget.py           # Virtualized QTableView hex/ascii inspector & chunk tree
        ├── metadata_view.py        # Tag table, BEXT/iXML trees & artwork renderer
        ├── loudness_view.py        # Broadcast level meters & compliance matrix
        └── styles.py               # Professional Dark Theme QSS console styling
```

---

## 3. Installation & Local Development

### Prerequisites
- Python 3.11 or later
- Operating System: macOS 12+, Windows 10/11 (64-bit), or Linux (x86_64 / arm64)

### Setup Virtual Environment
```bash
# Clone the repository
git clone https://github.com/your-org/audioscope.git
cd audioscope

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\Activate.ps1

# Install core dependencies
pip install -r requirements.txt
```

### Launch Application
```bash
python run.py

# Or pass an audio file directly to inspect on launch:
python run.py /path/to/recording.wav
```

---

## 4. Standalone Distribution & Packaging Pipelines

### A. macOS Standalone App Bundle & DMG (`.app` / `.dmg`)
Automated via `packaging/build_macos.sh`:
- Bundles all required Qt dynamic frameworks and PyAV `.dylib` files inside `AudioScope.app/Contents/Frameworks`.
- Configures `Info.plist` with `CFBundleIdentifier` (`com.audioscope.analyzer`), `NSHighResolutionCapable`, and `CFBundleDocumentTypes` for universal audio format associations.
- Generates a mountable, compressed `.dmg` disk image with an `/Applications` shortcut.

```bash
bash packaging/build_macos.sh
# Outputs:
#   dist/AudioScope.app
#   dist/AudioScope.dmg
```

### B. Windows Standalone Executable & Installer (`.exe`)
Automated via `packaging/build_windows.ps1`:
- Bundles Microsoft Visual C++ runtime DLLs, FFmpeg/PyAV dynamic libraries, and application icon (`assets/icon.ico`).
- Integrates Per-Monitor V2 DPI awareness and long path support.
- If Inno Setup (`ISCC.exe`) is installed, automatically compiles `dist/AudioScope-Setup-1.0.0.exe`.

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
# Outputs:
#   dist/AudioScope/AudioScope.exe (Portable folder)
#   dist/AudioScope-Setup-1.0.0.exe (Inno Setup Installer)
```

### C. Master PyInstaller Specification (`packaging/audioscope.spec`)
- Dynamic library discovery for `av` package: `collect_dynamic_libs('av')`.
- Hidden imports for `pyloudnorm`, `scipy.signal`, `scipy.special`, `mutagen`, `PySide6`.
- Custom runtime hook (`packaging/rthook_qt.py`) guaranteeing proper `QT_PLUGIN_PATH` and DLL search order in frozen environments.

---

## 5. Broadcast Compliance Standards Reference

| Standard / Target | Target Integrated Loudness | Tolerance | Max True Peak | Max Short-Term |
| :--- | :--- | :--- | :--- | :--- |
| **EBU R128** | -23.0 LUFS | ±0.5 LU | -1.0 dBTP | -18.0 LUFS |
| **ATSC A/85 (CALM)** | -24.0 LKFS | ±1.0 LU | -2.0 dBTP | — |
| **Spotify / YouTube** | -14.0 LUFS | ±1.0 LU | -1.0 dBTP | — |
| **Apple Music** | -16.0 LUFS | ±1.0 LU | -1.0 dBTP | — |
| **Amazon / Tidal** | -14.0 LUFS | ±1.0 LU | -1.0 dBTP | — |
| **Netflix Delivery** | -27.0 LUFS | ±1.0 LU | -2.0 dBTP | — |

---

## 6. License
MIT License. See [LICENSE](LICENSE) for details.
