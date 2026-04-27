# EXPLAINER

### 1. The Ledger

**Query:**
```python
aggs = merchant.transactions.aggregate(
    total_credits=Coalesce(Sum('amount', filter=Q(type='CREDIT')), 0),
    total_debits=Coalesce(Sum('amount', filter=Q(type='DEBIT')), 0)
)
balance = aggs['total_credits'] - aggs['total_debits']
```

**Why modeled this way?**
I used an immutable, append-only `Transaction` ledger (event sourcing). By having independent `CREDIT` and `DEBIT` transaction entries, the `Merchant` balance is strictly derived from the sum of atomic events rather than storing an updated `balance` integer that can drift. When a payout is requested, a `DEBIT` transaction is immediately recorded. If the payout fails, a compensating `CREDIT` transaction is recorded to return the funds. This guarantees the sum of credits minus debits always perfectly equals the available balance, satisfying the strict data integrity requirement.

### 2. The Lock

**Code:**
```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    
    # ... balance calculation and sufficient funds check ...
    
    payout = Payout.objects.create(...)
    Transaction.objects.create(type='DEBIT', ...)
```

**Primitive:**
It relies on the `SELECT ... FOR UPDATE` database row-level locking primitive. By executing `select_for_update()` inside a `transaction.atomic()` block, the specific `Merchant` row in PostgreSQL is locked until the transaction commits or rolls back. If two simultaneous payout requests arrive, the first transaction acquires the lock, while the second request is forced to block and wait. When the first finishes, its `DEBIT` transaction is committed. The second request then acquires the lock, re-calculates the `balance` using the newly updated ledger, and will cleanly reject the request if funds are insufficient.

### 3. The Idempotency

**How it knows:**
The system checks if a `Payout` record already exists with the given `idempotency_key` (scoped per `merchant`) and a `created_at` timestamp within the last 24 hours.

**In-flight collision:**
Because the idempotency check is executed *after* acquiring the `select_for_update()` lock on the `Merchant`, concurrency is safely handled. If the first request is in flight and processing, it holds the lock on the `Merchant`. The second request will wait for the lock. Once the first request completes and releases the lock, the second request resumes, queries the DB, finds the `Payout` that the first request just committed, and returns the exact same 200 OK response without executing any logic.

### 4. The State Machine

**Check for failed-to-completed:**
In `tasks.py` inside `process_payout_task`:
```python
with transaction.atomic():
    payout = Payout.objects.select_for_update().get(id=payout_id)
    
    # Ensure it hasn't been completed or failed by another worker
    if payout.status != 'PROCESSING':
        return
```
And at the beginning of the task:
```python
# State machine guard: only pending or processing can be processed
if payout.status not in ['PENDING', 'PROCESSING']:
    logger.info(f"Payout {payout_id} in {payout.status} state, ignoring.")
    return
```
Because the task acquires a lock on the `Payout` row and verifies that its status is strictly `'PROCESSING'` before allowing transitions to `'COMPLETED'` or `'FAILED'`, it rejects any attempt to move backwards or from a terminal state like `'FAILED'`.

### 5. The AI Audit

**Subtly wrong code (Wrong locking placement with Idempotency):**
The AI initially tried to perform the idempotency check *before* starting the `transaction.atomic()` block and acquiring the row lock on the merchant:
```python
# AI suggested this:
existing_payout = Payout.objects.filter(merchant_id=merchant_id, idempotency_key=key).first()
if existing_payout:
    return Response(...)

with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    # ...
```

**What I caught:**
I realized this introduces a race condition. If two requests arrive at the exact same millisecond, they both query for `existing_payout`, both find `None`, and both proceed to block on the `select_for_update()` lock. While the lock would prevent them from overdrawing if funds ran out, if the merchant had plenty of funds, *both* payouts would be created since the idempotency check had already been passed. The `UniqueConstraint` on `(merchant, idempotency_key)` would catch it via a database error, but it's a messy exception rather than a clean idempotent return.

**What I replaced it with:**
I moved the idempotency check *inside* the `transaction.atomic()` block, explicitly after acquiring the lock on `Merchant`:
```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    
    existing_payout = Payout.objects.filter(merchant=merchant, idempotency_key=idempotency_key).first()
    if existing_payout:
        return Response(PayoutSerializer(existing_payout).data, status=status.HTTP_200_OK)
    # ...
```
This guarantees that one request completes its check, logic, and insert before the second request even begins its idempotency check.
