#!/usr/bin/env bash
# Run the KB validators (schema lint + cross-reference check).
# Auto-selects an interpreter so this works the same locally and in CI:
#   - local Mac:  uses the project .venv (where the deps live)
#   - CI / other: falls back to python3, then python (setup-python provides a shim)
# Usage: ./scripts/validate.sh   (run before every commit; must exit 0)
set -euo pipefail
cd "$(dirname "$0")/.."

if   [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then PY=python3
else PY=python; fi

# Bootstrap the small validator dependency set if missing, so a fresh checkout
# never fails with "missing dep (jsonschema)".
if ! "$PY" -c 'import jsonschema, yaml' 2>/dev/null; then
  "$PY" -m pip install -q pyyaml 'jsonschema>=4.18'
fi

"$PY" scripts/lint.py && "$PY" scripts/xref.py
