# 🧠 Technical Explainer: Payout Engine Architecture

This document outlines the architectural decisions and engineering primitives used to ensure the system remains consistent, concurrent-safe, and self-healing.

## 1. The Ledger (Event Sourcing)

**Logic:**
$$Balance = \sum Credits - \sum Debits$$

**Why modeled this way?**
I used an immutable, append-only `Transaction` ledger. By having independent `CREDIT` and `DEBIT` entries, the Merchant balance is strictly a derived state.
- **Integrity:** Storing a single balance integer is prone to "drift" over time.
- **Auditability:** Every single Paise movement is backed by a transaction record.
- **Compensating Transactions:** If a payout fails, we don't just "undo" a number; we record a new `CREDIT` transaction. This satisfies the strict financial requirement for a non-destructive audit trail.

## 2. The Lock (Concurrency Control)

**Primitive:** `SELECT ... FOR UPDATE`

**Execution:**
By wrapping the balance check and debit creation inside a `transaction.atomic()` block using `select_for_update()`, the system places a **Row-Level Lock** on the specific Merchant in PostgreSQL.
- **Race Condition Prevention:** If two payout requests hit the API for the same merchant at the exact same millisecond, the first acquires the lock. The second request is forced to block and wait.
- **Stale Data Prevention:** Once the first request commits, the second request wakes up, re-calculates the balance (now seeing the new debit), and correctly rejects the request if funds are now insufficient.

## 3. Idempotency (The 24-Hour Guard)

**Collision Handling:**
The idempotency check is executed **after** acquiring the `select_for_update()` lock.
1. Request A acquires the lock and begins processing.
2. Request B (a retry) waits for the lock.
3. Request A completes, creating a Payout record with a unique key.
4. Request B acquires the lock, checks the database, finds the existing Payout record, and returns a cached `200 OK` response without repeating the financial logic.

## 4. Infrastructure Resilience: State Reconciliation

**The "Orphaned Task" Problem:**
In a distributed system (like Render + Celery), workers can crash or "spin down" while a task is in flight. This leaves a payout stuck in a `PROCESSING` state—a "zombie" record that holds funds but will never complete.

**The Solution:**
I implemented a **Self-Healing Reconciliation Logic** in the system's initialization (`seed.py`).
- **Automatic Healing:** Every time the server boots, it scans for orphaned payouts in the `PROCESSING` state.
- **Administrative Rescue:** It transitions these "ghosts" to a terminal state (`COMPLETED` or `FAILED`) based on the system state, ensuring the merchant's "Held Balance" is eventually cleared.

## 5. Frontend Stability: Polling vs. Race Conditions

**The "Flickering" Bug:**
With real-time polling via `setInterval`, a race condition occurs when a user switches merchants. A background "refresh" for the old merchant might return after the user has switched to the new merchant, causing the UI to "flicker" back to the old data.

**The Fix:**
- **Decoupled State:** Separated `activeMerchantId` from the fetched merchant object.
- **Memoized Polling:** Used `useCallback` and `useEffect` hooks dependent on the `activeMerchantId`. This ensures that any background request that doesn't match the current ID is ignored, providing a stable and responsive user experience.

## 6. The AI & Framework Audit (Senior Catch-List)

**Catch #1: Django ProtectedError during DB Resets**
- *The Bug:* Attempting to delete a Merchant would crash the system if they had existing Payouts due to `on_delete=models.PROTECT`.
- *The Fix:* I re-engineered the deletion hierarchy in the seed script to follow a "Child-First" cleanup: `Payout` $\rightarrow$ `Transaction` $\rightarrow$ `Merchant`.

**Catch #2: Django CheckConstraint Syntax**
- *The Bug:* AI suggested the `condition` keyword (hallucination).
- *The Fix:* Corrected to `check=Q(...)` to prevent migration-time crashes.

**Catch #3: Concurrency Testing in TransactionTestCase**
- *The Bug:* Standard `TestCase` rolls back transactions, meaning child threads in a test cannot "see" the lock.
- *The Fix:* Implemented `TransactionTestCase` to force real database commits during the concurrency test suite.

## 7. Production Math: The "Paise" Rule

To avoid the infamous floating-point error where $0.1 + 0.2 = 0.30000000000000004$, this engine performs all calculations using **integers (Paise/Cents)**. Conversion to decimal INR is only performed at the "Presentation Layer" (the Frontend), ensuring the core financial logic is mathematically perfect.

---
*Architected for accuracy. Built for resilience.*
