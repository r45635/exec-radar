"""pytest configuration – add all package source roots to sys.path."""

import sys
from pathlib import Path

# Repository root (one level above this file)
_ROOT = Path(__file__).parent

# Make all package namespaces importable without editable installs
for _pkg in [
    "packages/schemas/schemas",
    "packages/collectors/collectors",
    "packages/normalizers/normalizers",
    "packages/rankers/rankers",
    "packages/notifications/notifications",
    "apps/api",
]:
    _path = str(_ROOT / _pkg)
    if _path not in sys.path:
        sys.path.insert(0, _path)
