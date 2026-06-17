#!/usr/bin/env sh
# Container entrypoint: wait for PostgreSQL, optionally migrate, then exec the
# given command (gunicorn for the web service, manage.py commands for workers).
set -e

echo "Waiting for database to be ready..."
python <<'PYEOF'
import os
import sys
import time

import psycopg

url = os.environ.get("DATABASE_URL", "postgresql://jurnale:jurnale@db:5432/jurnale")
last = None
for _ in range(60):
    try:
        psycopg.connect(url).close()
        print("Database is ready.")
        break
    except Exception as exc:  # noqa: BLE001
        last = exc
        time.sleep(2)
else:
    print(f"Database not reachable after 120s: {last}", file=sys.stderr)
    sys.exit(1)
PYEOF

# Only the web service sets RUN_MIGRATIONS=1, so migrations run exactly once.
# --fake-initial lets an already-populated legacy database be adopted safely.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "Applying migrations..."
    python manage.py migrate --fake-initial --noinput
fi

exec "$@"
