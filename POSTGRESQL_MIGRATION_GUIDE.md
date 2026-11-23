# RidesAI — PostgreSQL Migration & Production Deployment Guide

This guide documents the production-ready PostgreSQL configuration and zero-data-loss migration pipeline for the RidesAI Django DRF backend (`ridesai_backend/`).

---

## 1. Database Configuration Overview

`ridesai_backend/config/settings.py` resolves `DATABASES["default"]` in the following priority order:

1. **Explicit SQLite opt-in (`USE_SQLITE=True`):** Uses local `ridesai_backend/db.sqlite3` (for offline local testing or reading legacy SQLite data during migration).
2. **`DATABASE_URL` (Recommended for Production & Local PostgreSQL):** Parsed via `dj-database-url` with persistent connection pooling (`CONN_MAX_AGE=600` by default), `CONN_HEALTH_CHECKS=True`, and optional TLS (`DB_SSL_REQUIRE=True`).
3. **Discrete PostgreSQL Variables (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`):** Used automatically if `DATABASE_URL` is omitted and `DB_NAME` is set.
4. **Default Fallback:** Falls back to `db.sqlite3` only if neither `DATABASE_URL` nor `DB_NAME` is configured.

---

## 2. Required Environment Variables (`ridesai_backend/.env`)

Copy `ridesai_backend/.env.example` to `ridesai_backend/.env` and configure the following variables (never commit `.env` to Git):

```env
# --- Core Django ---
DJANGO_SECRET_KEY=<generate-50+-char-random-secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=api.yourdomain.com,yourdomain.com
SITE_URL=https://yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# --- PostgreSQL Database ---
# Primary connection string (recommended)
DATABASE_URL=postgresql://<db_user>:<db_password>@<db_host>:5432/ridesai_db
DB_CONN_MAX_AGE=600
DB_SSL_REQUIRE=True          # Set False for local PostgreSQL without SSL
USE_SQLITE=False

# Optional discrete vars (only if DATABASE_URL is not set)
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=ridesai_db
# DB_USER=ridesai_user
# DB_PASSWORD=<strong-password>
# DB_HOST=localhost
# DB_PORT=5432

# --- AI Voice & Agent Keys ---
OPENAI_API_KEY=<openai-api-key>
OPENAI_MODEL=gpt-4o-mini
GROQ_API_KEY=<groq-api-key>
GROQ_STT_MODEL=whisper-large-v3

# --- WhatsApp Cloud API / Evolution ---
WHATSAPP_GRAPH_API_VERSION=v21.0
WHATSAPP_VERIFY_TOKEN=<webhook-verify-token>
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=<evolution-api-key>

# --- Billing (Polar) ---
POLAR_API_URL=https://api.polar.sh
POLAR_ACCESS_TOKEN=<polar-live-access-token>
POLAR_WEBHOOK_SECRET=<polar-webhook-secret>
POLAR_MOCK_MODE=False

# --- SMTP Email (OTP & Password Reset) ---
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=<sender@yourdomain.com>
EMAIL_HOST_PASSWORD=<smtp-app-password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=RidesAI <sender@yourdomain.com>
```

---

## 3. Provisioning PostgreSQL (Fresh Server or Local)

### Step A: Create Database & User in PostgreSQL

```sql
-- Connect via psql as postgres superuser:
CREATE USER ridesai_user WITH PASSWORD 'replace_with_strong_password';
CREATE DATABASE ridesai_db OWNER ridesai_user ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE ridesai_db TO ridesai_user;
```

*(Note: For running `python manage.py test` against PostgreSQL, grant `CREATEDB` to your local dev user: `ALTER USER ridesai_user CREATEDB;`)*

### Step B: Install Python Dependencies

```bash
cd ridesai_backend
python -m pip install -r requirements.txt
```

This installs `psycopg2-binary` and `dj-database-url` alongside Django and DRF dependencies.

---

## 4. Executing the Zero-Data-Loss Migration (SQLite → PostgreSQL)

### Option 1: Automated 6-Step Migration Script (Recommended)

Run the built-in pipeline script from `ridesai_backend/`:

```bash
# Optional dry-run (backs up SQLite, exports fixture, verifies PG connection without writing):
python scripts/migrate_sqlite_to_postgres.py --dry-run

# Execute full zero-data-loss migration:
python scripts/migrate_sqlite_to_postgres.py
```

The script automatically performs:
1. **Timestamped Backup:** Saves `ridesai_backend/backups/db.sqlite3.backup.<timestamp>` (excluded from Git via `.gitignore`).
2. **UTF-8 Fixture Export:** Runs `dumpdata --natural-foreign --natural-primary` with `USE_SQLITE=True` and `PYTHONUTF8=1` (preserving Urdu, Roman Urdu, and emoji text), excluding `contenttypes`, `auth.permission`, `admin.logentry`, and `sessions.session`.
3. **PostgreSQL Schema Creation:** Verifies live PostgreSQL connectivity and runs `python manage.py migrate --noinput`.
4. **Clean Data Load:** Removes migration-seeded `Plan` duplicates on fresh databases and imports the fixture via `manage.py loaddata` (with `raw=True` guards active on `operations/signals.py` to prevent duplicate auto-prints or rider reassignments).
5. **Sequence Reset:** Executes `sqlsequencereset` across all installed apps inside an atomic transaction so primary key auto-increment sequences never collide on new `INSERT`s.
6. **Row-Count Integrity Check:** Compares row counts across all 40 project models (`accounts`, `billing`, `companies`, `operations`, `employee`) between SQLite and PostgreSQL and exits non-zero if any mismatch is detected.

### Option 2: Fresh Production Deployment (No SQLite Data to Transfer)

If deploying to a brand-new production database with no legacy SQLite data:

```bash
cd ridesai_backend
python manage.py check --deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

---

## 5. Post-Migration Verification Checklist

- [ ] **Connectivity:** `python manage.py check` reports `System check identified no issues (0 silenced).`
- [ ] **Migration Parity:** `python manage.py makemigrations --check --dry-run` reports `No changes detected`.
- [ ] **Row-Count Parity:** All models in `accounts`, `billing`, `companies`, `operations`, and `employee` match 100% between SQLite and PostgreSQL.
- [ ] **Sequence Health:** Creating a new `Order`, `Company`, or `AgentConversation` succeeds without `duplicate key value violates unique constraint`.
- [ ] **Automated Test Suite:** `python manage.py test accounts billing operations` passes 100% against PostgreSQL.
- [ ] **Exempt Billing & Multi-Tenant Check:** Verify `ayeshaarshed145@gmail.com` exemption, monthly voice quotas, Owner AI Pause/Resume, and tenant isolation on live PostgreSQL.
- [ ] **Production Security:** Confirm `DJANGO_DEBUG=False`, `POLAR_MOCK_MODE=False`, `DB_SSL_REQUIRE=True`, and HTTPS headers (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) are enabled behind your reverse proxy/load balancer.
- [ ] **Scheduled Jobs:** Schedule `python manage.py send_billing_reminders` once daily via cron / systemd timer / Task Scheduler.
