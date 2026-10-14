#!/usr/bin/env bash
# Install everything Ripple needs into .venv and ui/node_modules.
# Offline-first: uses vendor/wheels (Linux x86_64, cp312/cp313) and vendor/npm-cache.
# Falls back to the network when the vendored artifacts don't match the platform.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY=""
for cand in python3.12 python3.13 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    v=$("$cand" -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
    if [[ "$v" == "3.12" || "$v" == "3.13" ]]; then PY="$cand"; break; fi
  fi
done
if [[ -z "$PY" ]] && command -v uv >/dev/null 2>&1; then
  uv python install 3.12 && PY="$(uv python find 3.12)"
fi
[[ -z "$PY" ]] && { echo "Need Python 3.12 or 3.13" >&2; exit 1; }
echo "[setup] python: $PY ($($PY --version))"

if [[ ! -x .venv/bin/python ]]; then "$PY" -m venv .venv; fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then .venv/bin/python -m ensurepip -q; fi

# vendor/ only holds Linux x86_64 artifacts (the cloud build box). Other platforms use the network.
OFFLINE=0
[[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]] && OFFLINE=1

if [[ $OFFLINE == 1 ]] && .venv/bin/python -m pip install -q --no-index --find-links vendor/wheels -r requirements.lock; then
  echo "[setup] python deps installed offline from vendor/wheels"
else
  echo "[setup] offline install failed, trying network" >&2
  .venv/bin/python -m pip install -q -r requirements.lock
fi
# Make the repo root importable (the `ripple` package) without a build step.
SITE=$(.venv/bin/python -c 'import sysconfig;print(sysconfig.get_paths()["purelib"])')
echo "$ROOT" > "$SITE/ripple_repo.pth"

if command -v npm >/dev/null 2>&1 && [[ -f ui/package-lock.json ]]; then
  ( cd ui && ([[ $OFFLINE == 1 ]] && npm ci --offline --cache ../vendor/npm-cache --no-audit --no-fund >/dev/null \
      && echo "[setup] ui deps installed offline") \
    || (npm ci --no-audit --no-fund >/dev/null && echo "[setup] ui deps installed from network") \
    || echo "[setup] WARNING: ui deps not installed" >&2 )
fi

echo "[setup] smoke test:"
.venv/bin/python scripts/verify_falkordb.py
