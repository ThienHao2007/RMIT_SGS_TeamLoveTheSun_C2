#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$SCRIPT_ROOT"

echo "========================================================="
echo "  QUORUM-GOVERNED API GUARD - SETUP"
echo "========================================================="
echo "Requires Python 3.12+ and Node.js 22.12+ with npm on PATH."
echo "Existing administrator keys and databases are preserved."
echo ""

python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 'Python 3.12+ is required.')"
node -e "const [major, minor] = process.versions.node.split('.').map(Number); if (major < 22 || (major === 22 && minor < 12)) { console.error('Node.js 22.12+ is required.'); process.exit(1); }"

echo "[1/4] Creating the local Python environment..."
python3 -m venv .venv
".venv/bin/python" -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 'The .venv environment requires Python 3.12+.')"

echo "[2/4] Installing Python dependencies..."
".venv/bin/python" -m pip install -r requirements-dev.txt

echo "[3/4] Installing and building the UI..."
npm --prefix ui ci
npm --prefix ui run build

echo "[4/4] Generating missing administrator keypairs..."
".venv/bin/python" scripts/gen_keys.py

echo ""
echo "Setup completed. Run these commands from any directory:"
printf '  %q %q\n' "$SCRIPT_ROOT/.venv/bin/python" "$SCRIPT_ROOT/run.py"
printf '  %q %q\n' "$SCRIPT_ROOT/.venv/bin/python" "$SCRIPT_ROOT/demo.py"
