# Rides AI - Phase 2 Billing Architecture (Stripe + PostgreSQL Ready)

## 1. Standard Flow
- 3-day free trial on registration.
- After 3 days, dashboard locks until a card is attached via Stripe.
- Automated monthly deductions.

## 2. Manual Override (Ayesha's Case)
- Hardcoded check for specific email(s).
- Bypasses 3-day trial and checkout. Grants immediate 1-month active access.
- After 1 month, override expires, dashboard locks, and prompts to attach a card for future Stripe automation.

## 3. Payment Failure & Grace Period
- If automated payment fails, grant a 3-day grace period with a red dashboard warning.
- If unresolved after grace period, pause the AI agent and lock dashboard.

---

## Legacy Billing Notes (Deprecated)

This delivery uses multi-business self-service Polar billing by default. For local development only, `POLAR_MOCK_MODE=True` with `DJANGO_DEBUG=True` enables a clearly labelled local test checkout. It records a `paid_test` transaction and a `mock_sub_...` subscription without contacting Polar or charging money. The mock route is blocked when DEBUG is false. It is not a substitute for signed Polar webhooks or production payment verification.

The remainder of this section describes the legacy single-client manual billing design and is not the active configuration.

### Single-client manual billing notes

This package defaults to `RIDESAI_SINGLE_CLIENT_MODE=True`. In this mode, the public plans endpoint returns an empty list, registration accepts no plan, verification does not start Polar checkout, and Polar checkout/cancel/resume endpoints are disabled.

Client journey: register → verify email → administrator approval → 30-day initial access → manual renewal submission → administrator approval → next 30-day access period. A 3-day grace period begins at the due date; after it ends, access is suspended on the next access check.

Manual payment submissions are stored in `billing.ManualPayment`. Admin can review them in the custom Admin dashboard's Manual Payments view or Django Admin. Approving a payment clears the past-due/suspended state and extends access by 30 days.

Message allowance defaults to 1,000 messages per 30-day period. Admin can change `Company.message_limit`. The AI agent must invoke the quota service `billing.services.consume_company_message(company)` before processing each accepted customer message. No agent message processor exists yet in this archive, so this integration remains a Day 2 task.

Business Gmail setup is client self-service: the dashboard links to Google account creation / Workspace and records the business email address, domain and setup status. It does not provision mailboxes or store Google credentials.

Configure `MANUAL_PAYMENT_INSTRUCTIONS` with the real payment instructions and `DEFAULT_CLIENT_MESSAGE_LIMIT` with the agreed message allowance. Never hardcode credentials.
