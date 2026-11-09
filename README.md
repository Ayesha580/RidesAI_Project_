# RidesAI — Single-client deployment package

This archive represents the **single-client Day 1 delivery variant**. Billing uses manual payment review; Polar subscription checkout is disabled in this mode. The AI customer-support message processor, order lifecycle and rider delivery workflow are not included in this archive and are not claimed complete.

## Requirements
- Windows 10/11, PowerShell
- Python 3.12+ (the configured requirements allow Django 5.2 through 6.x)
- Node.js/npm compatible with Vite 8 (Node 20.19+ or 22.12+ recommended)
- SMTP credentials only if sending verification emails through a real mail server

## Backend setup (PowerShell)
```powershell
cd .\ridesai_backend
py -0p
# Choose the installed Python path suitable for the project:
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env` and set a long random `DJANGO_SECRET_KEY`; configure `DJANGO_ALLOWED_HOSTS`, `SITE_URL`, CORS origins and approved `MANUAL_PAYMENT_INSTRUCTIONS`. The example email backend prints verification mail to the terminal for local development. Do not use `DJANGO_DEBUG=True` in production.

Before migrating any real/shared database, make a database backup and review the migration plan. For a fresh local development database:
```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
python manage.py createsuperuser
python manage.py runserver
```
Backend API is served at `http://127.0.0.1:8000/`. Admin at `/admin/`.

## Frontend setup (separate PowerShell window)
```powershell
cd .\frontend
npm ci
npm run lint
npm run build
npm run dev
```
Vite normally runs at `http://localhost:5173`. Confirm the API base URL in `src/api/axiosClient.js` matches the backend address. If npm install fails, verify Node/npm and network access before running the build.

## Single-client operational flow
1. Owner registers and verifies the email (24-hour verification link).
2. Administrator reviews and approves the company; approval starts initial 30-day access.
3. Owner submits manual payment evidence in Settings → Billing.
4. Administrator reviews and approves/rejects payment. Approval renews access for 30 days.
5. A three-day grace period follows expiry; access suspends after grace on an access check.
6. The business message allowance is configurable in Django Admin. The future AI message handler must invoke `billing.services.consume_company_message(company)` before processing inbound customer messages.

## Secrets and data
Never commit `.env`, live API credentials, bank details, customer documents, or production database files. Use `.env.example` as a template. Store uploads in a protected production storage service and define access/retention policies. Configure HTTPS, secure cookies, host allowlists and production logging before release.

See `SUBMISSION_STATUS.md`, `TEST_REPORT.md`, `CHANGELOG.md`, and `KNOWN_LIMITATIONS.md` for qualification and limitations.
