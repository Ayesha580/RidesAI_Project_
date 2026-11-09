# RidesAI — single-client delivery handoff

This ZIP is a client-specific variant of RidesAI. It preserves the existing React/Django application while switching the client-facing billing experience to manual payments. It is not the future multi-client SaaS checkout release.

## Day 1 implementation

### Client registration and access
- Registration no longer asks the client to select a subscription plan.
- Email verification remains required. Verification no longer redirects to Polar checkout.
- The administrator reviews and approves the business. Approval starts a 30-day initial access period.
- After the access expiry, the account enters a 3-day grace period. On subsequent authenticated requests/login after the grace period, access is automatically suspended.
- Approval/payment/access are separate states.

### Manual payments
- Client submits transfer reference, optional amount/currency, optional proof file and notes from Settings → Billing.
- Admin reviews submissions in Admin → Manual Payments and approves or rejects them.
- Approval clears overdue/suspended state and grants 30 days of access.
- The client-specific UI does not show plans or online checkout. Polar checkout and subscription-management endpoints return 404 in single-client mode.
- Receiving-account details are not invented. Configure `MANUAL_PAYMENT_INSTRUCTIONS` in the backend environment with the agreed transfer details.

### Message usage
- Company has an administrator-configurable monthly message limit (default 1,000) and usage counter.
- Owner billing dashboard displays used/remaining messages.
- `consume_company_message(company)` and `POST /api/billing/messages/consume/` provide the quota gate for the AI agent. The AI agent backend is not present in this project version, so the agent must call the quota service/API before accepting each message during Day 2 integration.
- Usage resets after each 30-day usage period.

### Business Gmail / Google Workspace
- Settings → Billing includes self-service links to Google account creation and Google Workspace.
- Client can save their business email address, domain and setup status in RidesAI.
- RidesAI does not create a Google mailbox automatically and never requests/stores Google passwords. A custom `@yourdomain.com` address requires domain ownership and Google Workspace.

## New/changed backend files
- `accounts/serializers.py` — plan_id optional for single-client registration.
- `accounts/views.py` — no plan assignment required in single-client mode; approval response includes access expiry.
- `billing/models.py` — `ManualPayment` record.
- `billing/views.py` / `billing/urls.py` — manual payment submission/review, business email settings, message quota hook, manual billing overview, and disabled Polar checkout actions.
- `billing/services.py` — 30-day access, 3-day grace/suspension, manual payment renewal, and message quota consumption.
- `billing/admin.py` — manual payment review in Django Admin.
- `companies/models.py` — access dates, message counters/limit and business email fields.
- `companies/admin.py` — admin-configurable message limit and access/email fields.
- `companies/migrations/0004_single_client_access_and_business_email.py` — new company fields.
- `billing/migrations/0002_manual_payment.py` — manual payment table.
- `config/settings.py`, `.env.example` — single-client mode, default quota and payment instructions.
- Frontend registration, verification, billing settings and admin companies page updated for this client flow.

## Configuration
Set these backend environment values before using the client build:

```env
RIDESAI_SINGLE_CLIENT_MODE=True
DEFAULT_CLIENT_MESSAGE_LIMIT=1000
MANUAL_PAYMENT_INSTRUCTIONS=Please contact the RidesAI administrator for current bank transfer details.
```

Change the message limit to the agreed client allowance and replace the payment-instructions placeholder with the actual approved transfer instructions. Do not place bank credentials or Google passwords in source code.

## Database handoff
New migrations are included. The package also inherits pending migrations from the earlier billing/email-verification work:
- `accounts.0005_email_verification`
- `companies.0003_plan_polar_product_id_currency`
- `companies.0004_single_client_access_and_business_email`
- `billing.0001_initial`
- `billing.0002_manual_payment`

The local/shared database migrations were not applied as part of this ZIP preparation. The authorised developer/database administrator must review the migration plan and apply migrations in the target environment. No production database or credentials were accessed.

## Validation performed for this package
- Python `compileall` syntax validation: passed.
- JavaScript/JSX syntax parsing across 39 source files using the installed TypeScript parser: passed with zero syntax errors.
- Full Django `manage.py check` and automated test suite could not be rerun in this Linux packaging environment: the bundled Windows virtual environment is not executable here (Django package import is incomplete on this host). The previous local project report recorded 4 passing tests before these new Day 1 changes; those results do not test the new manual billing features.
- Vite production build could not run because frontend dependencies were not fully installed in this environment (`vite` executable unavailable).
- No live SMTP, Google Workspace provisioning, payment transfer, production migration or end-to-end client login was tested.

## Day 2 integration requirement
The existing AI Agent/Conversations pages are placeholders and there is no message-processing backend in this archive. When the agent endpoint is implemented, it must call `consume_company_message(company)` before processing each inbound customer message and return HTTP 429 when the monthly quota is exhausted.

The archive includes the original `db.sqlite3` copied from the supplied project ZIP, unchanged. It is included only as the project's original local database copy; do not overwrite any active/shared database with it. The Windows virtual environment and incomplete local `node_modules` directory are intentionally excluded from the deliverable ZIP.
