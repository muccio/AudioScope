#!/usr/bin/env bash
# ==============================================================================
# AudioScope - All-in-One Local Build Script
# Automatically creates virtual environment, installs dependencies, and compiles
# the standalone executable for the current platform (macOS .app/.dmg or Linux).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# 1. Verify and Find a Working Python 3 Interpreter
PYTHON_BIN=""
find_working_python() {
    local candidates=()
    if [ -n "${PYTHON:-}" ]; then
        candidates+=("${PYTHON}")
    fi
    candidates+=(python3 python3.12 python3.11 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3)

    for py in "${candidates[@]}"; do
        if command -v "${py}" &> /dev/null; then
            local test_out
            test_out="$("${py}" -c "import sys; sys.stdout.write('OK')" 2>/dev/null || true)"
            if [ "${test_out}" = "OK" ]; then
                command -v "${py}"
                return 0
            fi
        fi
    done
    return 1
}

if ! PYTHON_BIN="$(find_working_python)"; then
    echo "Error: No working python3 interpreter found in PATH."
    exit 1
fi

echo "=========================================================="
echo " AudioScope: Local Build Pipeline"
echo " Platform: $(uname -s) ($(uname -m))"
echo " Python:   $("${PYTHON_BIN}" --version 2>&1) (${PYTHON_BIN})"
echo "=========================================================="

# 2. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv with ${PYTHON_BIN}..."
    "${PYTHON_BIN}" -m venv .venv
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

# 3. Upgrade pip and install requirements
echo "Installing dependencies..."
if command -v uv &> /dev/null; then
    echo "Found uv: installing dependencies using uv pip..."
    uv pip install --python .venv/bin/python -r requirements.txt pyinstaller
else
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt pyinstaller
fi

# 4. Run PyInstaller / Packaging Script
OS_NAME="$(uname -s)"

if [ "${OS_NAME}" = "Darwin" ]; then
    echo "Detected macOS: running packaging/build_macos.sh..."
    bash packaging/build_macos.sh
elif [ "${OS_NAME}" = "Linux" ]; then
    echo "Detected Linux: building standalone executable..."
    pyinstaller --noconfirm --clean packaging/audioscope.spec
    echo ""
    echo "Build completed successfully!"
    echo "Binary location: ${SCRIPT_DIR}/dist/AudioScope/AudioScope"
else
    echo "Unrecognized OS: ${OS_NAME}. Running standard PyInstaller spec..."
    pyinstaller --noconfirm --clean packaging/audioscope.spec
fi
