# Known Limitations

- Real OTP email delivery requires SMTP sender credentials. Configure an SMTP sender in `ridesai_backend/.env`; the recipient for the requested manual verification test is `hunnarhubb@gmail.com`. No credentials were supplied and no real message has been sent.
- In local development, `django.core.mail.backends.console.EmailBackend` emits the OTP into the backend terminal; this is not inbox delivery.
- This delivery is configured for `RIDESAI_SINGLE_CLIENT_MODE=True`; single-client flow remains manual approval/payment oriented. The complete self-service Polar plan checkout flow is not part of the single-client mode.
- Django tests and frontend production build were not run because dependencies could not be installed in this environment.
- Full end-to-end operation, role/object permissions, order/rider lifecycle, and AI Agent behavior remain unverified and must not be represented as certified.
