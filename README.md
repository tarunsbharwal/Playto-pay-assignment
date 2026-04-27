# Playto Payout Engine

This is the backend and frontend for the Playto Payout Engine, a robust, concurrent, and idempotent payment processing engine.

## Stack
- Backend: Django, Django REST Framework, Celery, Redis
- Frontend: React (Vite), Tailwind CSS
- Database: PostgreSQL

## Features Included
1. **Merchant Ledger**: Computes balance strictly from an append-only transaction ledger.
2. **Payout API**: Fully idempotent and concurrent-safe using `SELECT FOR UPDATE` and DB-level constraints.
3. **Background Processing**: A robust Celery worker simulates bank settlement, with retry logic and state guards.
4. **React Dashboard**: Live-updating React frontend with a Merchant Switcher to toggle between different accounts (Acme Corp vs Globex Inc) and view independent ledger histories.

## Technical Deep Dive
For a detailed breakdown of how I handled concurrency locks, idempotency, and ledger integrity, please refer to [EXPLAINER.md](./EXPLAINER.md).

## Getting Started (Docker Compose) - Zero Friction Setup

We have containerized the entire stack (PostgreSQL, Redis, Django API, Celery Workers, and React Dashboard). The database migrations and initial seed data are applied automatically via the backend container's `entrypoint.sh` script.

### Prerequisites
- Docker and Docker Compose installed on your system.

### Step-by-Step Instructions

1. Open your terminal in the root of the project directory (where `docker-compose.yml` is located).
2. Run the following command to build and start the entire stack in the background:
   ```bash
   docker-compose up --build -d
   ```
3. **Wait 10-15 seconds** for the PostgreSQL database to initialize. The backend container (`playto_pay_backend`) will automatically detect when the database is healthy, then it will run:
   - `python manage.py makemigrations`
   - `python manage.py migrate`
   - `python seed.py` (Seeding "Acme Corp" and "Globex Inc" with starting balances)
4. The system is now fully operational!
   - **Frontend Dashboard**: Open [http://localhost:5173](http://localhost:5173) in your browser.
   - **Backend API**: Running at [http://localhost:8000/api/v1/](http://localhost:8000/api/v1/)
   
   *Verify Data*: If you open the dashboard and see "No merchants seeded," run this command to manually inject the test data:
   ```bash
   docker-compose exec backend python seed.py
   ```
5. To view the live logs of the Celery payout processor simulating bank settlements:
   ```bash
   docker-compose logs -f celery_worker
   ```
6. To gracefully stop the entire stack:
   ```bash
   docker-compose down
   ```

### Running the Concurrency & Idempotency Tests

The test suite explicitly verifies the `SELECT FOR UPDATE` row-level locks and 24-hour idempotency mechanisms. To run these tests inside the running Docker container:

```bash
docker-compose exec backend python manage.py test core
```

### Local Setup Without Docker (Alternative)

If you prefer to run it locally without Docker:
1. Ensure PostgreSQL and Redis are running locally.
2. In `backend/`:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   export DB_NAME=playto_pay DB_USER=postgres DB_PASSWORD=yourpassword
   python manage.py migrate
   python seed.py
   python manage.py runserver
   ```
3. Run the celery workers in separate terminal windows:
   ```bash
   celery -A config worker --loglevel=info
   celery -A config beat -l info
   ```
4. In `frontend/`:
   ```bash
   npm install
   npm run dev
   ```
