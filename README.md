# RidesAI — Multi-business SaaS delivery package

This version is configured for **multiple independent businesses**. Each business owner manages their own team, roles, modules, permissions, orders, riders, AI agent and subscription. There is no platform-admin approval dashboard or admin payment-review workflow.

## Included in this implementation

- Six-digit email OTP registration, expiry, resend cooldown and single-use verification.
- Self-service plan selection after OTP verification and Polar checkout/webhook billing.
- Subscription overview, payment history, cancellation/resume and a three-day grace period.
- A daily billing reminder management command (must be scheduled on the host).
- Owner-managed staff accounts and custom role/module/permission assignment.
- Backend-enforced staff permissions, including rider-only assigned deliveries and sequential delivery status updates.
- Company-scoped order, order-item, delivery assignment and audit-event records.
- Company-scoped AI conversations, catalogue/order context, human handover, public chat link, action allowlist and action logs.
- Browser-native voice input and spoken assistant replies on the public customer agent and owner test console (speech-to-text → existing AI backend → text-to-speech).
- Monthly AI message quota consumption before agent processing.

The implementation uses the existing React/Vite frontend and Django REST Framework backend. This is an implementation candidate, not a certified production-ready release. Some older business modules (for example appointments, attendance, reports, suppliers and returns) remain dashboard placeholders. The PRD items not yet implemented are listed in `IMPLEMENTATION_ACCEPTANCE_MATRIX.md`.

## Requirements

- Windows 10/11 or Linux/macOS
- Python 3.12+
- Node.js 20.19+ or 22.12+
- Polar sandbox/live credentials
- SMTP sender credentials (Gmail App Password or another SMTP provider) for real inbox OTP delivery
- OpenAI API key for natural-language AI Agent responses

## Backend setup (PowerShell)

```powershell
cd .\ridesai_backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` before starting. Required values for real integrations:

```env
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
SITE_URL=http://localhost:5173
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=<your-sender@gmail.com>
EMAIL_HOST_PASSWORD=<your-Gmail-App-Password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=<your-sender@gmail.com>

POLAR_API_URL=https://sandbox-api.polar.sh
POLAR_ACCESS_TOKEN=<Polar-sandbox-access-token>
POLAR_WEBHOOK_SECRET=<Polar-webhook-secret>
POLAR_MOCK_MODE=False

OPENAI_API_KEY=<OpenAI-API-key>
OPENAI_MODEL=gpt-4o-mini
```

The `.env.example` contains placeholders only. Never commit `.env`, provider keys, app passwords, production databases or customer documents. For OTP inbox delivery, configure the sender email and app password in `.env`; if you have no SMTP credentials during local development, set `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` and copy the printed six-digit code from the backend terminal (this does not send an inbox email). For a local UI-flow demonstration without a Polar account, set these values in `ridesai_backend/.env`:

```env
DJANGO_DEBUG=True
POLAR_MOCK_MODE=True
POLAR_ACCESS_TOKEN=
POLAR_WEBHOOK_SECRET=
```

Then restart Django. The app will show a clearly labelled test checkout and activate a test-only subscription with no charge. It also supports local cancel/resume so you can demonstrate the billing screens. This mode is rejected whenever `DJANGO_DEBUG=False`. It is not a payment integration and must never be enabled in production. To use real Polar checkout, set `POLAR_MOCK_MODE=False` and provide matching sandbox/live credentials and a public signed-webhook endpoint. The example Standard monthly Polar product ID/price is seeded by migration; verify that the product ID and displayed price match your Polar workspace before accepting live payments. Configure the Polar webhook to `https://<your-api-host>/api/billing/webhook/` and subscribe to checkout, order and subscription lifecycle events.

Then run:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
python manage.py runserver
```

The backend API runs at `http://127.0.0.1:8000/`.

## Frontend setup (separate PowerShell window)

```powershell
cd .\frontend
npm ci
npm run lint
npm run build
npm run dev
```

Vite normally runs at `http://localhost:5173`. Set `VITE_API_URL=http://127.0.0.1:8000/api` if your backend runs elsewhere.

## Main flows

1. Business owner registers; the app redirects to `/verify-email?email=...` and displays the six-digit OTP entry form. The code expires after five minutes and resend is rate-limited.
2. If an owner reaches login before verifying, entering valid credentials displays both **Enter verification code** and **Resend verification email** actions. The verification page also lets the owner enter their email if opened directly.
3. OTP verification activates the business account without a platform-admin approval step.
4. Owner selects a plan and completes Polar checkout. Signed Polar webhooks and the checkout verification endpoint update subscription state.
5. Later logins route an active subscriber directly to the owner dashboard.
6. Owner creates staff accounts, sets credentials, creates roles and selects dashboard modules plus backend action permissions.
7. Rider roles should normally receive `my_deliveries` plus `deliveries.view_assigned` and `deliveries.update_status`; the backend scopes reads and updates to that rider's assignments.
8. Owner enables the AI Agent, chooses allowed actions, and shares the public customer chat URL shown on the AI Agent page.
9. AI messages are stored per business and consume that business's message quota. Configure `OPENAI_API_KEY` for model-generated answers.

## Billing reminders

Run this command once daily using Windows Task Scheduler or cron:

```powershell
python manage.py send_billing_reminders
```

The command sends at most one reminder per business per grace-period day and records sends to avoid duplicate reminders. The app's authenticated access checks suspend a business after the three-day grace period; a successful subscription renewal clears the overdue state.

## Important operational notes

- Back up the target database before applying migrations to an existing installation.
- Test Polar in sandbox first. Live checkout/webhook behavior cannot be verified without your live provider credentials and a publicly reachable HTTPS webhook endpoint.
- Real OTP inbox delivery cannot be verified until valid SMTP sender credentials are configured. The previous embedded SMTP credential has been removed from this archive; rotate it before use.
- The public AI chat endpoint is rate-limited. Public order creation and order lookup are only enabled when the owner explicitly enables those actions. Order prices are loaded from the business catalogue, not accepted from the public caller.
- The AI chat service uses company-scoped catalogue and order records. Do not add secrets or private customer data to the system prompt.
- Voice is browser-native: browser speech recognition supplies the transcript, the existing backend AI endpoint processes it, and browser speech synthesis reads the returned response. It is not a dedicated real-time voice/telephony provider; browser support varies. See `IMPLEMENTATION_ACCEPTANCE_MATRIX.md`.
