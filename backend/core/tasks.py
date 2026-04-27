import random
import time
import logging
from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Payout, Transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_payout_task(self, payout_id):
    """
    Picks up a payout and moves it through the lifecycle.
    Simulates bank settlement: 70% succeed, 20% fail, 10% hang.
    """
    try:
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)

            # State machine guard: only PENDING or PROCESSING can be processed
            if payout.status not in ('PENDING', 'PROCESSING'):
                logger.info(f"Payout {payout_id} in {payout.status} state, skipping.")
                return

            if payout.status == 'PENDING':
                payout.status = 'PROCESSING'
                payout.attempts += 1
                payout.save(update_fields=['status', 'attempts', 'updated_at'])
    except Payout.DoesNotExist:
        logger.warning(f"Payout {payout_id} not found.")
        return

    # Simulate bank processing delay
    time.sleep(2)

    # Simulate bank settlement outcome
    outcome = random.random()

    if outcome < 0.10:
        # 10% — Hang in processing. The sweep job will pick this up.
        logger.info(f"Payout {payout_id} simulating hang in processing.")
        return

    try:
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)

            if payout.status != 'PROCESSING':
                logger.info(f"Payout {payout_id} no longer PROCESSING, skipping.")
                return

            if outcome < 0.80:
                # 70% — Success (0.10 to 0.80)
                payout.status = 'COMPLETED'
                payout.save(update_fields=['status', 'updated_at'])
                logger.info(f"Payout {payout_id} completed successfully.")
            else:
                # 20% — Failure (0.80 to 1.00)
                # Atomically: mark failed AND return funds in one transaction
                payout.status = 'FAILED'
                payout.save(update_fields=['status', 'updated_at'])

                Transaction.objects.create(
                    merchant=payout.merchant,
                    amount=payout.amount,
                    type='CREDIT',
                    payout=payout,
                    description=f"Refund for failed payout {payout.id}"
                )
                logger.info(f"Payout {payout_id} failed, funds returned.")
    except Payout.DoesNotExist:
        pass


@shared_task
def sweep_stuck_payouts():
    """
    Finds payouts stuck in PROCESSING for >30 seconds and retries them.
    Uses exponential backoff with max 3 attempts.
    """
    cutoff = timezone.now() - timedelta(seconds=30)
    stuck_payouts = Payout.objects.filter(
        status='PROCESSING',
        updated_at__lt=cutoff
    )

    for payout in stuck_payouts:
        retry_stuck_payout.delay(str(payout.id))
    
    if stuck_payouts.exists():
        logger.info(f"Found {stuck_payouts.count()} stuck payouts, queued for retry.")


@shared_task
def retry_stuck_payout(payout_id):
    """Retry a single stuck payout with exponential backoff, max 3 attempts."""
    try:
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)

            if payout.status != 'PROCESSING':
                return

            if payout.attempts >= 3:
                # Max retries exhausted — fail and return funds atomically
                payout.status = 'FAILED'
                payout.save(update_fields=['status', 'updated_at'])

                Transaction.objects.create(
                    merchant=payout.merchant,
                    amount=payout.amount,
                    type='CREDIT',
                    payout=payout,
                    description=f"Refund: payout {payout.id} failed after {payout.attempts} attempts"
                )
                logger.info(f"Payout {payout_id} failed after max retries, funds returned.")
            else:
                payout.attempts += 1
                payout.save(update_fields=['attempts', 'updated_at'])
                
                # Schedule retry with exponential backoff: 2^attempt seconds
                backoff_delay = 2 ** (payout.attempts + 1)
                process_payout_task.apply_async(
                    args=[str(payout.id)],
                    countdown=backoff_delay
                )
                logger.info(f"Retrying stuck payout {payout_id} in {backoff_delay}s (attempt {payout.attempts})")
    except Payout.DoesNotExist:
        pass
