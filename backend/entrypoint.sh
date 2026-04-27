#!/bin/sh

echo "Running database migrations..."
python manage.py makemigrations
python manage.py migrate

echo "Seeding initial merchants and credits..."
python seed.py

echo "Starting Django server..."
exec python manage.py runserver 0.0.0.0:8000
