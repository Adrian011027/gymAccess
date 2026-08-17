#!/bin/sh
set -e

echo "[entrypoint] esperando a postgres en ${DB_HOST}:${DB_PORT:-5432}..."
python - <<'PY'
import os, sys, time
import psycopg

host = os.environ['DB_HOST']
port = os.environ.get('DB_PORT', '5432')
dsn = f"host={host} port={port} dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} password={os.environ['DB_PASSWORD']}"

for intento in range(30):
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
        print("[entrypoint] postgres listo")
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint] intento {intento + 1}/30: {e}")
        time.sleep(2)

print("[entrypoint] postgres no respondio a tiempo")
sys.exit(1)
PY

echo "[entrypoint] aplicando migraciones..."
python manage.py migrate --noinput

echo "[entrypoint] recolectando estaticos..."
python manage.py collectstatic --noinput --clear

echo "[entrypoint] arrancando: $*"
exec "$@"
