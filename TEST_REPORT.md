# Test report

## Executed in this packaging pass

- `python -m compileall -q ridesai_backend`: PASS (Python syntax compilation).
- Manual source inspection confirms the voice controls are wired into the public agent and owner test console, and order creation endpoints reject create-order actions unless the caller sends an explicit confirmation flag. This is not a substitute for browser/API integration tests.
- TypeScript parser syntax pass over the frontend JavaScript/JSX source files: PASS.

## Not executed

- Django system checks, migration consistency checks, migrations and automated tests: NOT RUN because Django is not installed in this packaging environment.
- Frontend lint and Vite production build: NOT RUN; `npm ci` did not complete within the available execution window, so no production bundle was produced.
- Browser-based frontend/backend integration tests: NOT RUN.
- Real Gmail OTP delivery: NOT RUN; requires SMTP sender credentials.
- Polar checkout and webhook signature round-trip: NOT RUN; requires Polar sandbox credentials and reachable webhook endpoint.
- AI Agent model responses: NOT RUN; requires OpenAI API key.

## Added automated tests (not yet run)

- Business order isolation by company.
- Rider sees only assigned deliveries.
- Rider can advance assigned delivery through allowed statuses and cannot change another order or cancel it.
- Existing OTP and billing tests remain in the project.


## Business configuration revision verification
- `python -m compileall -q ridesai_backend`: passed (syntax compilation only).
- Relative frontend import path audit: passed after adding case-compatible re-export modules.
- Django runtime checks, migrations, and automated tests: not run; Django is not installed in the execution environment.
- Frontend production build: not run; `npm ci` timed out and Vite was not installed, so `npm run build` could not start.
- New tests were added for tenant isolation, delivery-zone rejection/fee calculation, and collection orders, but are not yet executed.
- No live SMTP, Polar, OpenAI, browser microphone/speech, WhatsApp or external integration test was performed.


## Follow-up verification UX patch
- Python syntax compilation: PASS (`compileall` and AST parse).
- Frontend production build: NOT RUN successfully in this packaging environment; the dependency install timed out and the local `vite` executable was unavailable. Re-run `npm ci` then `npm run build` on the target Windows machine.
- Django runtime checks and test suite: NOT RUN in this packaging environment because Django is not installed here. Run `python manage.py check`, `python manage.py migrate`, and `python manage.py test` inside the project's Python virtual environment.
- Live Gmail delivery: NOT VERIFIED; requires a valid Gmail App Password in `ridesai_backend/.env` and outbound SMTP access.
- Added regression coverage for email-as-username login and immediate retry after a failed SMTP resend; tests are present but not executed here because Django is unavailable in this packaging environment.


## Follow-up implementation changes in this archive

- Added a development-only mock checkout, local test subscription activation, test transaction history, and local cancel/resume behavior. This requires `POLAR_MOCK_MODE=True` and `DJANGO_DEBUG=True`; no payment is taken.
- Added regression tests for mock checkout activation, idempotent completion, and local cancel/resume. These tests are present but **not executed** because Django is not installed in this packaging runtime.
- Exposed `orders.view_all` and `orders.assign` in the owner permission catalogue; manager role templates already include these grants.
- `python -m compileall -q ridesai_backend`: PASS after these changes.
- Frontend build remains unverified because Vite is not available in the extracted `node_modules` and `npm ci` did not complete in the available execution window.
