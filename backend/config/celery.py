import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'sweep-stuck-payouts-every-minute': {
        'task': 'core.tasks.sweep_stuck_payouts',
        'schedule': 30.0, # Run every 30 seconds
    },
}
