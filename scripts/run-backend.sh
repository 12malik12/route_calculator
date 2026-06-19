#!/usr/bin/env bash
# Bootstraps and runs the Django backend.
# The Python virtualenv is not persisted across file syncs, so we recreate it
# automatically whenever it is missing.
set -e

cd "$(dirname "$0")/../backend"

if [ ! -x ".venv/bin/python" ]; then
  echo "[run-backend] virtualenv missing, creating it..."
  uv venv --python 3.13
  uv pip install -r requirements.txt
fi

echo "[run-backend] applying migrations..."
.venv/bin/python manage.py migrate --run-syncdb --noinput >/dev/null 2>&1 || true

echo "[run-backend] starting Django on http://127.0.0.1:8000"
exec .venv/bin/python manage.py runserver 0.0.0.0:8000
