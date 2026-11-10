# Known limitations and external dependencies

- Real OTP delivery requires a valid SMTP sender and app password in `ridesai_backend/.env`. The archive includes placeholders only; no real inbox delivery has been performed in this environment.
- Real Polar checkout and signed webhooks require a matching sandbox/live access token, product ID and webhook secret, plus a publicly reachable HTTPS webhook endpoint. No live payment was made or verified here. A local mock checkout can exercise the UI flow only; it does not charge money or verify Polar.
- AI natural-language answers require `OPENAI_API_KEY`. The backend and customer chat endpoint are integrated, but no live model response was verified without a key.
- The daily billing reminder command must be scheduled by the deployment host; Django does not run it automatically.
- Browser-native voice input/output is included as a baseline; browser support varies. Dedicated telephony, streaming voice and WhatsApp voice notes are not included.
- Existing older modules such as appointments, attendance, reports, suppliers, returns, prescriptions, etc. still include placeholder screens or legacy code. The new working workflows in this pass focus on staff roles/permissions, catalogue access, orders, delivery assignment/status, billing and AI conversations.
- Full Django tests and migration checks have not been executed in this packaging environment because Django is not installed here. The frontend production build is also unverified: the available Vite executable was unavailable and dependency installation did not complete. Python syntax compilation is not a substitute for runtime testing.
- The application is not certified production-ready until migrations are reviewed/applied to a backed-up database, provider credentials are configured, and the full registration/payment/order/rider/AI flow is tested on a deployed staging environment.


## Additional business configuration and operations revision
Business owners now have CRUD APIs and a workspace for business locations, weekly operating hours, city/country/radius service areas, and approved FAQs/policies/support entries. Delivery orders must match an active configured service area; radius areas require latitude/longitude. Employee/team assignment and staff assigned-order filtering are included. AI context now contains approved knowledge, hours, locations and service areas, and its tone/greeting/support contact can be configured. These additions have not been run against a live Django database in this environment because Django dependencies are not installed. The frontend production build also remains unverified because the Vite package could not be installed before the dependency-install timeout.
