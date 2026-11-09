#!/usr/bin/env bash
# ==============================================================================
# AudioScope macOS Standalone Application Bundle & DMG Generation Script
# Target: macOS 12+ (Apple Silicon arm64 & Intel x86_64)
# Output: dist/AudioScope.app and dist/AudioScope.dmg
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== AudioScope macOS Standalone Packaging Pipeline ==="
echo "Project Root: ${PROJECT_ROOT}"

# 1. Environment & Architecture Validation
OS_NAME="$(uname -s)"
ARCH="$(uname -m)"
echo "Detected Platform: ${OS_NAME} (${ARCH})"

# 2. Virtual Environment Check
if [ -d "${PROJECT_ROOT}/.venv" ]; then
    echo "Activating virtual environment at ${PROJECT_ROOT}/.venv..."
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.venv/bin/activate"
elif [ -d "${HOME}/.venv" ]; then
    echo "Activating virtual environment at ${HOME}/.venv..."
    # shellcheck disable=SC1091
    source "${HOME}/.venv/bin/activate"
fi

if ! command -v pyinstaller &> /dev/null; then
    echo "Error: pyinstaller is not installed in the active environment."
    echo "Install dependencies with: pip install -r requirements.txt pyinstaller"
    exit 1
fi

# 3. Clean prior build artifacts
echo "Cleaning previous build and dist artifacts..."
rm -rf "${PROJECT_ROOT}/build" "${PROJECT_ROOT}/dist"

# 4. Verify Icon
ICON_PATH="${PROJECT_ROOT}/packaging/assets/icon.icns"
if [ ! -f "${ICON_PATH}" ]; then
    echo "Warning: ${ICON_PATH} not found. Generating default icon..."
    python3 -c "from PIL import Image; Image.new('RGBA', (512, 512), (0, 210, 255, 255)).save('${ICON_PATH}')"
fi

# 5. Run PyInstaller
echo "Running PyInstaller with audioscope.spec..."
cd "${PROJECT_ROOT}"
pyinstaller --noconfirm --clean "${PROJECT_ROOT}/packaging/audioscope.spec"

APP_PATH="${PROJECT_ROOT}/dist/AudioScope.app"

if [ "${OS_NAME}" != "Darwin" ]; then
    echo "Notice: Non-macOS environment detected (${OS_NAME})."
    echo "PyInstaller completed compilation for ${OS_NAME} in dist/AudioScope."
    echo "To build native macOS .app and .dmg, run this script directly on macOS."
    exit 0
fi

# 6. Verify .app Bundle Structure
if [ ! -d "${APP_PATH}" ]; then
    echo "Error: AudioScope.app was not generated in dist/!"
    exit 1
fi

echo "Verifying AudioScope.app bundle structure..."
FRAMEWORKS_DIR="${APP_PATH}/Contents/Frameworks"
RESOURCES_DIR="${APP_PATH}/Contents/Resources"
PLIST_PATH="${APP_PATH}/Contents/Info.plist"

mkdir -p "${FRAMEWORKS_DIR}" "${RESOURCES_DIR}"

# Ensure icon is present in Resources
cp -f "${ICON_PATH}" "${RESOURCES_DIR}/icon.icns"

# 7. Verify & Inject Info.plist audio document types if plutil exists
if command -v plutil &> /dev/null && [ -f "${PLIST_PATH}" ]; then
    echo "Validating Info.plist via plutil..."
    plutil -lint "${PLIST_PATH}"
fi

# 8. Create deployable DMG
echo "Generating AudioScope.dmg using hdiutil..."
DMG_STAGING="${PROJECT_ROOT}/dist/dmg_staging"
rm -rf "${DMG_STAGING}"
mkdir -p "${DMG_STAGING}"

# Copy .app into staging
cp -R "${APP_PATH}" "${DMG_STAGING}/"

# Add /Applications symlink for drag-and-drop installation
ln -s /Applications "${DMG_STAGING}/Applications"

DMG_OUTPUT="${PROJECT_ROOT}/dist/AudioScope.dmg"
rm -f "${DMG_OUTPUT}"

hdiutil create \
    -volname "AudioScope" \
    -srcfolder "${DMG_STAGING}" \
    -ov \
    -format UDZO \
    "${DMG_OUTPUT}"

rm -rf "${DMG_STAGING}"

echo "========================================================"
echo " macOS Build Completed Successfully!"
echo " Standalone App Bundle: ${APP_PATH}"
echo " Deployable Disk Image: ${DMG_OUTPUT}"
echo "========================================================"
