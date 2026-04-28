#!/bin/bash
# 1. Run migrations and seed data
python manage.py migrate
python seed.py

# 2. Start Celery in the background (the '&' is crucial)
celery -A config worker --loglevel=info &

# 3. Start Django using Gunicorn in the foreground
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT