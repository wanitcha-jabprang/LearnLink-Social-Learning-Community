#!/bin/sh
set -e

echo "Waiting for database to be ready..."
python manage.py shell -c '
import time, sys
from django.db import connections
from django.db.utils import OperationalError

for attempt in range(30):
    try:
        connections["default"].ensure_connection()
        print("Database is ready.")
        sys.exit(0)
    except OperationalError:
        time.sleep(2)

print("Database unavailable after 60s.", file=sys.stderr)
sys.exit(1)
'

python manage.py migrate --noinput
python manage.py createcachetable
python manage.py collectstatic --noinput

exec "$@"