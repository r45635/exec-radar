#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# archive_project.sh — Create a timestamped zip of the Exec Radar project
#
# Usage:
#   ./archive_project.sh
#
# Output:
#   zip/exec-radar_YYYYMMDDHHMMSS.zip
# ---------------------------------------------------------------------------
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
ZIP_DIR="${PROJECT_DIR}/zip"
ARCHIVE="${ZIP_DIR}/${PROJECT_NAME}_${TIMESTAMP}.zip"

mkdir -p "$ZIP_DIR"

cd "$PROJECT_DIR"

zip -r "$ARCHIVE" . \
    -x "./zip/*" \
    -x "./.venv/*" \
    -x "./.git/*" \
    -x "./__pycache__/*" \
    -x "*/__pycache__/*" \
    -x "./.pytest_cache/*" \
    -x "*/.pytest_cache/*" \
    -x "*.pyc"

echo ""
echo "Archive created: ${ARCHIVE}"
echo "Size: $(du -h "$ARCHIVE" | cut -f1)"
