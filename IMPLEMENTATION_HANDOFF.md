# RidesAI multi-business implementation handoff

## Product access model

- Multi-business SaaS with Polar subscriptions is the only supported billing mode.
- There is no platform-admin approval dashboard or manual payment review workflow.
- Business email OTP verification activates the business account; the owner then selects a Polar plan.
- Existing owner/staff accounts remain linked to one company. New order, delivery, conversation and agent action records are company-scoped.

## Staff and permissions

- `StaffRole` now stores both dashboard `modules` and granular backend `permissions`.
- Owners can provision staff credentials, assign roles and enable/disable staff.
- The backend checks module grants and permission grants separately.
- Rider template roles receive assigned-delivery access and sequential delivery status updates only.
- Orders and delivery records are scoped to the logged-in user's company. Rider reads are scoped to their own assignments.

## Orders and delivery APIs

- `GET/POST /api/operations/orders/`
- `PATCH /api/operations/orders/<id>/status/`
- `GET /api/operations/deliveries/`
- `GET /api/operations/deliveries/my/`
- `POST /api/operations/deliveries/assign/`
- `GET /api/operations/deliveries/riders/`
- `GET /api/operations/orders/catalog/`

Order status changes create audit events. Rider status transitions are limited to assigned → picked up → on the way → delivered.

## AI Agent APIs

- `GET/PATCH /api/operations/agent/settings/`
- `POST /api/operations/agent/chat/` (authenticated dashboard chat)
- `GET/PATCH /api/operations/agent/conversations/`
- `GET /api/operations/public/agent/<public_id>/catalog/` (rate-limited public catalogue)
- `POST /api/operations/public/agent/<public_id>/chat/` (rate-limited public customer chat)
- `GET /api/operations/public/agent/<public_id>/conversation/<conversation_id>/` (public conversation refresh)

The agent context is built from the current company's available catalogue items and matching customer orders. Conversations and action logs are stored with company foreign keys. Owner-enabled public actions are restricted to supported operations and validated against the business catalogue. Natural-language generation requires `OPENAI_API_KEY`; without it, the endpoint returns a configuration fallback rather than pretending an AI response was generated.

## Billing

- Polar checkout and webhook integration remain in the billing app.
- Standard monthly plan is seeded by migration; verify its product ID and price against the Polar workspace.
- Payment transaction history is returned in the billing overview.
- A three-day grace period is tracked for past-due/ended subscriptions. `send_billing_reminders` sends once-daily reminders and must be scheduled by the host.
- Polar is the only subscription payment path; the legacy manual-review flow is not exposed.

## Migrations

New migrations added:
- `accounts.0007_staffrole_permissions`
- `accounts.0008_seed_staff_role_permissions`
- `accounts.0009_add_orders_to_existing_roles`
- `companies.0005_company_agent_settings`
- `companies.0006_seed_default_polar_plan`
- `billing.0003_billingreminder`
- `operations.0001_initial`
- `operations.0002_agentconversation_customer_phone`

Before deploying, back up the target database and run `python manage.py makemigrations --check --dry-run`, `python manage.py migrate --plan`, `python manage.py migrate`, and `python manage.py test` in the target environment.

## Business configuration completion pass
New endpoints (authenticated business owner, tenant-scoped):
- `GET/POST/PATCH/DELETE /api/companies/locations/`
- `GET/POST/PATCH/DELETE /api/companies/hours/`
- `GET/POST/PATCH/DELETE /api/companies/service-areas/`
- `GET/POST/PATCH/DELETE /api/companies/knowledge/`
- `POST /api/companies/knowledge/{id}/approve/`
- `POST /api/companies/delivery-eligibility/`

Order assignment endpoint: `POST /api/operations/orders/{id}/assign/` with `employee_id` or `team`. Requires `orders.assign`; employees assigned to a team see that team's orders. Staff with `orders.view_all` can see all business orders.

Delivery orders must include `fulfillment_type=delivery`, a full address, and a configured matching service area. City/country zones match their configured geographic labels; radius zones require latitude and longitude. Delivery fees are derived from the matching service area. Collection orders do not require a delivery zone.


## Local payment demonstration

For a demo without Polar credentials, set `POLAR_MOCK_MODE=True` and `DJANGO_DEBUG=True` in `ridesai_backend/.env`. The frontend opens `/mock-payment`, where the owner explicitly confirms a simulated payment. The backend creates a `paid_test` transaction and a `mock_sub_...` subscription. The simulator supports local cancel/resume and is rejected when DEBUG is false. It does not contact Polar or charge money.

## Workflow hardening

- Owner role editor now offers `orders.assign` and `orders.view_all`; the existing accounts migration adds these grants to pre-existing manager roles.
- Order status changes are constrained to the supported lifecycle. Riders can only advance assigned deliveries through picked up → on the way → delivered.
- Delivery fees are calculated only from the matched business service area. Collection orders are always zero-fee, regardless of submitted customer data.
