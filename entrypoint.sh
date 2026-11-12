#!/bin/sh
set -e

echo "Waiting for MySQL..."

attempt=0
until python manage.py shell -c "from django.db import connection; connection.ensure_connection()" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        echo "MySQL did not become available after 60 seconds." >&2
        exit 1
    fi
    sleep 2
done

python manage.py migrate --noinput

python manage.py collectstatic --noinput

exec "$@"