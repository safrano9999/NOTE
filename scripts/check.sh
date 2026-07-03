#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
node --check "$root/index.js"
PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/note-pycache" python3 -m py_compile "$root/note/store.py"
python3 -m unittest discover -s "$root/tests" -v
