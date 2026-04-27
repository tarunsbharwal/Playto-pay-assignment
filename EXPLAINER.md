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

### 5. The AI Audit (Logic & Framework Syntax)

**Catch #1: Django CheckConstraint Syntax Hallucination**
The AI initially provided code using the `condition` keyword for database-level constraints.

*The Bug:* In modern Django, `CheckConstraint` strictly requires the `check` keyword. Using `condition` causes a `TypeError` that crashes the `makemigrations` process.

*The Fix:* I manually audited the `models.py` and corrected all constraints to use the `check=Q(...)` syntax, ensuring the database-level integrity guards actually deployed.

**Catch #2: Testing Deadlocks (TestCase vs TransactionTestCase)**
The AI confidently suggested a standard `TestCase` for concurrency testing with threads.

*The Bug:* Django’s `TestCase` wraps tests in a single transaction that is never committed. Because child threads use independent connections, they couldn't see the setup data, leading to false-positive test results where the lock wasn't actually being tested.

*The Fix:* I replaced it with `TransactionTestCase`, which forces a database commit, allowing the threads to actually contend for the `select_for_update` lock as they would in production.

### 6. The Frontend & Environment Audit

**Vite + Docker Networking**

*The Challenge:* The initial Docker setup used an outdated Node runtime and didn't account for how Vite binds to network interfaces.

*The Solution:* I upgraded the frontend to `node:20-alpine` and configured Vite to listen on `0.0.0.0`. This allowed the Windows host browser to successfully route requests to the containerized Vite dev server.

**API Response "Unwrapping"**

*The Bug:* The frontend was stuck on a "Loading" state because it expected a raw array of merchants. However, Django REST Framework (DRF) often wraps lists in a pagination object (e.g., `{"count": X, "results": []}`).

*The Fix:* I implemented a defensive "unwrapping" logic in the React fetch calls to detect both raw arrays and DRF paginated objects, ensuring the dashboard renders correctly regardless of backend pagination settings.
