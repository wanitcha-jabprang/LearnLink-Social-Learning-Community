#!/bin/sh

echo "Waiting for MySQL..."

sleep 10

python manage.py migrate
python manage.py createcachetable

python manage.py collectstatic --noinput || true

exec "$@"