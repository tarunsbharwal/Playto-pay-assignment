"""
Models for the Playto Payout Engine.

Design principles:
- Balance is NEVER stored. It is always derived from the Transaction ledger
  using database-level aggregation (SUM with FILTER).
- All money values are BigIntegerField in paise. No floats. No decimals.
- Concurrency is handled via SELECT FOR UPDATE on the Merchant row.
- State transitions are enforced by application code inside atomic blocks,
  backed by database CheckConstraints as a safety net.
- Transaction table is append-only. Entries are never updated or deleted.
"""

from django.db import models
from django.db.models import Sum, Q, CheckConstraint
from django.db.models.functions import Coalesce
import uuid


class Merchant(models.Model):
    """
    A merchant who receives international payments and requests INR payouts.
    
    IMPORTANT: There is intentionally NO balance column here.
    Balance is always computed from the Transaction ledger via DB aggregation.
    This eliminates any possibility of balance drift or stale cache.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    @property
    def balance(self):
        """
        Compute balance from the transaction ledger using DB-level aggregation.

        Generated SQL (PostgreSQL):
            SELECT
                COALESCE(SUM(amount) FILTER (WHERE type = 'CREDIT'), 0) -
                COALESCE(SUM(amount) FILTER (WHERE type = 'DEBIT'), 0)
            FROM core_transaction
            WHERE merchant_id = <this merchant>;

        This is the ONLY source of truth for balance. Never cache this value
        across requests — always recompute inside the atomic block.
        """
        aggs = self.transactions.aggregate(
            total_credits=Coalesce(
                Sum('amount', filter=Q(type='CREDIT')), 0,
                output_field=models.BigIntegerField()
            ),
            total_debits=Coalesce(
                Sum('amount', filter=Q(type='DEBIT')), 0,
                output_field=models.BigIntegerField()
            ),
        )
        return aggs['total_credits'] - aggs['total_debits']

    def __str__(self):
        return self.name


class Payout(models.Model):
    """
    A withdrawal request from a merchant.

    Lifecycle (state machine):
        PENDING → PROCESSING → COMPLETED   (happy path)
        PENDING → PROCESSING → FAILED      (bank rejection / timeout)

    Illegal transitions (enforced in application code inside atomic blocks):
        COMPLETED → anything
        FAILED → anything
        PROCESSING → PENDING

    Idempotency:
        (merchant, idempotency_key) is unique at the DB level.
        Keys are scoped per merchant with 24-hour application-level expiry.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name='payouts',
        help_text='The merchant requesting the withdrawal'
    )
    amount = models.BigIntegerField(
        help_text='Withdrawal amount in paise (integer, never float)'
    )
    bank_account_id = models.CharField(
        max_length=255,
        help_text='Destination bank account identifier'
    )
    idempotency_key = models.UUIDField(
        help_text='Client-supplied UUID for idempotent requests, scoped per merchant'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of processing attempts (for retry tracking)'
    )
    processing_started_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When the payout moved to PROCESSING. Used for stuck-payout detection.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Idempotency: one payout per (merchant, key) pair
            models.UniqueConstraint(
                fields=['merchant', 'idempotency_key'],
                name='unique_merchant_idempotency_key'
            ),
            # DB-level guard: amount must be positive
            models.CheckConstraint(
                check=models.Q(amount__gt=0),       # <-- CHANGED TO 'check'
                name='payout_amount_positive'
            ),
            # DB-level guard: status must be a valid choice
            models.CheckConstraint(
                check=models.Q(status__in=['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']),  # <-- CHANGED TO 'check'
                name='payout_status_valid'
            ),
        ]
        indexes = [
            # Hot path: sweep query for stuck payouts
            models.Index(
                fields=['status', 'updated_at'],
                name='idx_payout_status_updated',
            ),
            # Hot path: merchant's payout history
            models.Index(
                fields=['merchant', '-created_at'],
                name='idx_payout_merchant_created',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Payout {self.id} — {self.status} — {self.amount} paise"


class Transaction(models.Model):
    """
    Append-only ledger entry. Every money movement is recorded here.

    The merchant's balance is ALWAYS computed as:
        SUM(amount WHERE type='CREDIT') - SUM(amount WHERE type='DEBIT')

    Rules:
    - Transactions are NEVER updated or deleted (append-only ledger).
    - There is no updated_at field — intentionally immutable.
    - A DEBIT is created when a payout is requested (funds held).
    - A CREDIT is created when a payout fails (funds returned).
    - Customer payment CREDITs are seeded / simulated.

    The payout FK links a transaction to its originating payout,
    enabling full audit trail for every money movement.
    """
    class Type(models.TextChoices):
        CREDIT = 'CREDIT', 'Credit'
        DEBIT = 'DEBIT', 'Debit'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name='transactions'
    )
    amount = models.BigIntegerField(
        help_text='Amount in paise. Always positive — direction is indicated by type.'
    )
    type = models.CharField(
        max_length=6, choices=Type.choices,
        help_text='CREDIT increases balance, DEBIT decreases balance'
    )
    payout = models.ForeignKey(
        Payout, null=True, blank=True, on_delete=models.PROTECT,
        related_name='transactions',
        help_text='The payout this transaction belongs to (null for customer payments)'
    )
    description = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # NOTE: No updated_at. Ledger entries are immutable.

    class Meta:
        constraints = [
            # DB-level guard: amount must be positive
            CheckConstraint(
                check=Q(amount__gt=0),
                name='transaction_amount_positive'
            ),
            # DB-level guard: type must be valid
            CheckConstraint(
                check=Q(type__in=['CREDIT', 'DEBIT']),
                name='transaction_type_valid'
            ),
        ]
        indexes = [
            # Hot path: balance calculation per merchant
            models.Index(
                fields=['merchant', 'type'],
                name='idx_txn_merchant_type',
            ),
            # Hot path: merchant transaction history
            models.Index(
                fields=['merchant', '-created_at'],
                name='idx_txn_merchant_created',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} {self.amount} paise — {self.merchant.name}"
