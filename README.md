# 🚀 Playto Payout Engine

A robust, concurrent, and idempotent payment processing engine designed for financial data integrity. This system manages merchant ledgers through an append-only transaction architecture and uses background workers for simulated bank settlements.

## 🌐 Live Production Links
- **Live Dashboard (Vercel):** [https://playto-pay-assignment.vercel.app/](https://playto-pay-assignment.vercel.app/)
- **Live API (Render):** [https://playto-pay-assignment-1.onrender.com/api/v1/](https://playto-pay-assignment-1.onrender.com/api/v1/)

> ⚠️ **Note on Cold Starts:** This project is hosted on a free instance. Please allow ~50 seconds for the initial "cold start" wake-up when first opening the dashboard.

## 🛠️ Stack
- **Backend:** Django, Django REST Framework, Celery, Redis
- **Frontend:** React (Vite), Tailwind CSS
- **Database:** PostgreSQL (Cloud-hosted)
- **Deployment:** Docker, Vercel, Render

## ✨ Features Included
1. **Merchant Ledger:** Computes balance strictly from an append-only transaction ledger.
2. **Payout API:** Fully idempotent and concurrent-safe using `SELECT FOR UPDATE` and DB-level constraints.
3. **Background Processing:** A robust Celery worker simulates bank settlement, with retry logic and state guards.
4. **React Dashboard:** Live-updating frontend with a Merchant Switcher to toggle between accounts (Acme Corp vs Globex Inc) and view independent histories.

## 🧠 Technical Deep Dive

### 1. Atomic Ledger Integrity
Balances are never stored as a single mutable column. Instead, the balance is a derived state calculated from the transaction history:
$$Balance = \sum Credits - \sum Debits$$

### 2. Concurrency & Race-Condition Safety
To prevent "double-spending," the engine utilizes **Row-Level Locking** via `select_for_update()`. This ensures a merchant's ledger is locked during the deduction phase.

### 3. Self-Healing Reconciliation
Distributed systems can fail mid-task. I implemented a **State Reconciliation Logic** in `seed.py` that identifies orphaned payouts stuck in a `PROCESSING` state and reconciles them to ensure ledger consistency.

## 🐳 Getting Started (Docker Compose) - Zero Friction Setup
We have containerized the entire stack (PostgreSQL, Redis, Django API, Celery Workers, and React Dashboard).

### Prerequisites
- Docker and Docker Compose installed.

### Step-by-Step Instructions
1. Open your terminal in the root of the project directory.
2. Run the following command:
   ```bash
   docker-compose up --build -d
   ```
3. **Wait 10-15 seconds** for initialization. The backend will automatically run:
   - `python manage.py migrate`
   - `python seed.py` (Seeding Acme Corp & Globex Inc)
4. **Access the App:**
   - **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
   - **Backend API:** [http://localhost:8000/api/v1/](http://localhost:8000/api/v1/)

*Verify Data*: If you see "No merchants seeded," run:
```bash
docker-compose exec backend python seed.py
```

5. **View Live Logs** of the Celery worker:
```bash
docker-compose logs -f celery_worker
```

6. **Stop the stack:**
```bash
docker-compose down
```

## 🧪 Running the Concurrency & Idempotency Tests
The test suite verifies the `SELECT FOR UPDATE` locks and 24-hour idempotency mechanisms. Run these inside the Docker container:
```bash
docker-compose exec backend python manage.py test core
```

## 💻 Local Setup Without Docker (Alternative)
Ensure PostgreSQL and Redis are running locally.

**Backend Setup:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DB_NAME=playto_pay DB_USER=postgres DB_PASSWORD=yourpassword
python manage.py migrate
python seed.py
python manage.py runserver
```

**Run Celery (separate terminals):**
```bash
celery -A config worker --loglevel=info
celery -A config beat -l info
```

**Frontend Setup:**
```bash
cd frontend
npm install
npm run dev
```

## 📂 Project Structure
- `/backend`: Django core, REST API, and Celery task definitions.
- `/frontend`: React SPA with real-time polling.
- `EXPLAINER.md`: Deep dive into architectural locking and idempotency.

## 🚧 Production Considerations
- **Integer Math:** All financial calculations are handled in Paise to avoid floating-point inaccuracies.
- **Stateguards:** Transitions between Payout states (`PENDING` -> `PROCESSING` -> `COMPLETED`) are protected by logic to prevent illegal state jumps.

Built with a focus on Ledger Integrity and Scalable Architecture.
