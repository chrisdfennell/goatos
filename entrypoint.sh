#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate --fake-initial

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || python manage.py collectstatic --noinput

echo "Starting services..."
exec supervisord -c /etc/supervisord.conf
