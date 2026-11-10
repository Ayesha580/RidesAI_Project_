# Changelog

## Multi-business implementation pass

- Set SaaS/Polar subscription mode as the default configuration.
- Removed the platform-admin login/dashboard routes and manual-payment review API route from the application flow.
- Removed the embedded SMTP credential from `.env.example`; replaced with placeholders.
- Added granular staff role permissions, role permission templates and backend authorization checks.
- Added company-scoped orders, order items, rider assignments and order audit events.
- Added rider-only assigned delivery listing and sequential status updates.
- Added AI conversations, message history, action audit logs, owner-configurable action allowlist, public customer chat link and rate limiting.
- Added OpenAI environment configuration and business-scoped catalogue/order context.
- Added payment history to billing overview, three-day grace handling for ended subscriptions and a daily reminder command.
- Added default Polar plan seed migration and backend/frontend order, delivery and AI screens.


## Business configuration completion pass
- Added multi-location, weekly operating hours, service-area and approved knowledge models, serializers, tenant-scoped owner CRUD endpoints, and migration files.
- Added server-side delivery eligibility enforcement and service-area delivery fee calculation.
- Added employee/team order assignment, assignment history and assigned-only staff order visibility unless `orders.view_all` is granted.
- Extended owner profile and AI-agent configuration, and grounded AI responses in approved knowledge, hours, locations and service areas.
- Improved public order confirmation UI and delivery/collection details.
- Added frontend API filename aliases for case-sensitive builds.


## Email verification UX and delivery diagnostics
- Added a direct **Enter verification code** action to the login screen when the backend reports an unverified account.
- The verification screen now accepts an email address when opened directly, then accepts the six-digit OTP.
- Registration carries the backend's email-delivery result into the verification screen instead of always implying that an email was sent.
- Resend verification now returns an explicit delivery failure (HTTP 503) when SMTP fails for a known unverified account; the UI displays that failure.
- Login accepts either the account username or registered email address.
- Added a backend regression test for email-address login.
- Failed SMTP sends now invalidate the unsent token so an owner can retry immediately rather than being blocked by the 60-second resend cooldown.


## Billing simulator and workflow hardening

- Added a clearly labelled local-only mock payment checkout for demos without Polar credentials; mock activation, payment history, cancellation and resumption are tagged as test-only and are blocked when `DJANGO_DEBUG=False`.
- Local mock mode exposes active plans even when no Polar product IDs are configured.
- Exposed `orders.assign` and `orders.view_all` in the owner role-permission editor so manager grants can be assigned from the UI.
- Enforced allowed order lifecycle transitions and prevented customers from supplying their own delivery fee; collection orders always have zero delivery fee.
- Added tests for local mock billing, idempotent checkout confirmation, local cancel/resume, lifecycle transitions and collection-fee tampering. Tests have not been executed in this packaging environment.
