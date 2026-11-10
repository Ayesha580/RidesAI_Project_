# RidesAI delivery acceptance matrix

This matrix describes what is present in this archive, not a production certification.

| Requirement | Current implementation | Acceptance state |
|---|---|---|
| Business registration and six-digit email OTP | Registration, hashed OTP verification, expiry/attempt controls and resend flow; real delivery depends on SMTP configuration | Code present; inbox delivery unverified |
| Subscription plans, checkout and billing history | Polar checkout/webhook, plan selection, billing overview, payment history, cancel/resume; local development-only mock checkout is available when explicitly enabled | Code present; sandbox payment/webhook unverified; mock is not a real payment |
| Three-day grace period and suspension | Grace-state tracking and access checks; daily reminder command | Code present; scheduler and provider lifecycle unverified |
| Business owner staff accounts and role assignment | Owner-managed staff accounts, individual credentials, custom roles, module grants, granular API permissions, activation/deactivation and deletion | Code present; runtime tests unverified |
| Staff permission enforcement | Backend checks for order actions, catalog operations, delivery assignment, rider-only assigned deliveries and AI handover; manager assignment/view-all grants are seeded and exposed in the role permission catalogue | Code present; runtime tests unverified |
| Rider access | Company-scoped assigned-delivery list and restricted sequential status updates | Code present; runtime tests unverified |
| Business order workflow | Catalogue-backed orders, inventory decrement, order events, rider delivery assignment, employee/team assignment API and owner UI | Partial; print slips and category-specific fulfilment workflows are not complete |
| AI agent data grounding | Company-scoped catalogue, inventory, locations, operating hours, service areas, approved FAQ/policy/support context and matching customer order context; tone, greeting and support contacts are configurable | Code present; natural-language generation requires OpenAI key and live testing |
| Human handover | Conversation status, assignment, human reply UI/API and action audit records | Code present; live notifications are not integrated |
| Customer order confirmation | Public ordering UI shows an item/quantity subtotal and requires a customer confirmation checkbox before submitting; backend rejects unconfirmed actions | Partial; free-form conversational/voice order-summary state machine is not implemented |
| Voice input / AI processing / voice output | Browser speech recognition captures transcript; transcript uses the existing business AI API; browser speech synthesis reads returned assistant answer | Browser-dependent baseline only; no dedicated telephony/streaming voice provider |
| Delivery eligibility / zones | Owner CRUD for city, country and radius service areas; server-side city/country/radius matching, zone fee calculation and rejection of out-of-zone delivery orders | Implemented in code; migration and runtime tests still required. Radius checks require customer coordinates |
| Category-specific dashboards | Existing category-to-module configuration remains; shared catalogue and operations pages work across current business types | Partial; category-specific appointments, patient, kitchen, table, prescription and other workflows are not complete |
| Website embed and WhatsApp | Shareable public agent link exists | Not implemented for WhatsApp or embeddable website widget |
| Knowledge base / FAQ management and approved learning | Owner CRUD for FAQ, policy, procedure, approved-response and support entries; explicit approval endpoint; agent consumes approved active entries | Partial; controlled suggestions/analytics/retention learning workflow is not implemented |
| Notifications and printing | No complete configurable multi-channel order notification service or order-print slip workflow | Not implemented |
| Platform super-admin dashboard | Excluded in accordance with the project owner's instruction; PRD section 2.1/10 describes one | Intentionally excluded |

## Voice behavior

1. **Speech-to-text:** the browser's Web Speech recognition API transcribes a microphone recording into the existing message field.
2. **AI processing:** the transcript is submitted to the same company-specific backend AI conversation endpoint as typed text. OpenAI API credentials are required for model-generated natural-language answers.
3. **Text-to-speech:** the browser's speech synthesis API reads the actual assistant response returned by the backend.

Browser speech API availability and language support vary. Microphone permission is requested by the browser when the user presses Speak. This is not a hosted low-latency voice agent, PSTN/telephony integration, WhatsApp voice-note pipeline, or guaranteed cross-browser speech service.

## Changes in this revision

- Added tenant-scoped business locations and operating-hours CRUD endpoints and owner workspace UI.
- Added tenant-scoped city, country and radius delivery-area configuration; delivery orders are rejected unless they match an active configured area. Matching area delivery fees are set server-side rather than trusted from the customer payload.
- Added owner-managed FAQ, policy, procedure, approved-response and support-contact knowledge entries. Only active, approved entries are included in the AI context.
- Added configurable AI greeting, tone and support contact details. The AI system prompt now includes non-diagnostic health safeguards and rules for optional catalogue-grounded recommendations.
- Added employee/team order assignment, assignment history, and staff order-list scoping to assigned employee/team unless `orders.view_all` is granted. Manager roles receive assignment and view-all permissions through a migration.
- Extended owner profile editing to business name, category, business contact email, phone and address.
- Updated public and dashboard order forms to collect fulfilment details; public ordering displays the item subtotal and requires explicit confirmation before submitting. Delivery-zone validation is enforced by the backend.
- Added compatibility re-export files for case-sensitive frontend imports (`staffApi`, `profileApi`, `publicApi`).

## Staff permissions added in this package

- Added `orders.view_all` and `orders.assign` to the owner-visible permission catalogue so these grants can actually be assigned through the UI.
- Manager role templates and the existing `accounts.0010_order_assignment_permissions` migration include both grants.
- Riders remain scoped to their own assigned deliveries and sequential delivery status changes.

## Local mock payment

Set `POLAR_MOCK_MODE=True` only in a local `.env` where `DJANGO_DEBUG=True`. The UI labels the route as a test simulator. It creates a `paid_test` transaction and local subscription identifier, without contacting Polar or charging money. The backend rejects mock checkout when DEBUG is false. Real checkout still requires Polar credentials and signed webhook configuration.

## Before production acceptance

- Configure and test real SMTP, Polar and OpenAI credentials in a staging environment.
- Confirm Polar product IDs, prices, webhook event subscriptions and signature validation against the target Polar workspace.
- Install dependencies, run Django checks/migrations/tests and frontend lint/build; perform end-to-end browser tests.
- Complete business-category-specific workflows, website embedding, WhatsApp, controlled learning/FAQ suggestions and approval analytics, configurable notifications and printing.
- Confirm privacy/retention, operational monitoring, backups, deployment security and rate limits.
