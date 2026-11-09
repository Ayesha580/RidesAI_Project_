# Submission status

| Feature | Status | Evidence | Remaining work |
|---|---|---|---|
| Registration and business/owner persistence | Implemented (source review) | `accounts/views.py`, `accounts/serializers.py` | Full API tests required in supported Windows environment |
| Email verification | Implemented (source review) | Token hash, expiry and single-use logic; `accounts/tests.py` has 4 tests | Run suite; live SMTP is not verified |
| Owner login and approval redirect | Implemented (source review) | `accounts/views.py`, `billing/services.py` | Execute integration tests |
| Single-client initial 30-day access | Implemented (source review) | `billing/services.py`, company migration | Django migration/check execution blocked here |
| Manual payment submission and admin review | Implemented (source review) | `billing/models.py`, `billing/views.py`, `billing/services.py` | Verify permission and workflow tests |
| Grace period and suspension | Implemented (source review) | `billing/services.py` | Automated tests added but not run |
| Message quota service/API | Implemented as service/API hook | `billing/services.py`, billing API | AI handler is absent; quota enforcement not yet integrated into an AI processor |
| Business email / Workspace self-service details | Implemented (source review) | Billing settings APIs/UI | Google mailbox provisioning is not part of this delivery |
| Owner dashboard and staff/role UI | Partial | React owner/staff pages and Django staff APIs | End-to-end permissions and all screens need validation |
| Catalog/categories/items/deals/inventory | Partial | `companies/models.py`, `companies/views.py`, React Catalog component | No full inventory, CSV, or isolation tests yet |
| Orders and rider assignment/delivery | Missing in this archive | No corresponding order/rider app found in archive structure | Implement complete backend + UI workflows |
| AI customer-support agent / RAG | Missing in this archive | Handoff notes explicitly say processor is absent | Implement tenant-filtered retrieval, guarded actions, handoff and quota integration |
| Production configuration/security hardening | Partial | `.env.example`, settings review | Production deployment checklist, secrets, HTTPS, uploads/storage, security review and tests |
| Backend test suite execution | Blocked | Django not installed in execution environment; network package install unavailable | Run on project Windows environment with dependencies installed |
| Frontend production build/lint | Blocked | npm dependency install timed out; `vite` executable absent after partial install | `npm ci`, lint, build in network-enabled environment |
| Full integration and live service verification | Not verified | No live credentials/services available | Run full integration matrix in target environment |
