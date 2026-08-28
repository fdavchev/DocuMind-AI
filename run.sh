#!/usr/bin/env bash
# run.sh — start DocuMind AI with the correct interpreter (macOS/Linux/Git Bash).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$DIR/venv/Scripts/python.exe" ]; then
    PY="$DIR/venv/Scripts/python.exe"      # Windows layout
elif [ -x "$DIR/venv/bin/python" ]; then
    PY="$DIR/venv/bin/python"              # POSIX layout
else
    echo "No virtualenv found. Create it with: python -m venv venv && pip install -r requirements.txt" >&2
    exit 1
fi

exec "$PY" -m streamlit run "$DIR/app.py"
