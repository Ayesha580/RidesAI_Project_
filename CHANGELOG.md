# Changelog

## Package qualification updates
- Added 4 automated billing service tests for single-client approval/access, grace suspension, quota enforcement and manual renewal.
- Added root `README.md` with Windows PowerShell setup and deployment guidance.
- Added `SUBMISSION_STATUS.md`, `TEST_REPORT.md`, and `KNOWN_LIMITATIONS.md` with explicit test qualification and unverified areas.
- No application source rewrite performed; preserved the existing Django/React architecture and existing application logic.

## 2026-11-09 — Registration verification workflow
- Registration now generates a cryptographically random six-digit email OTP with a five-minute expiry and hashes the code before persistence.
- Added attempt counter and migration for OTP abuse limiting; verification rejects expired, used, or exhausted codes and binds OTP checks to the submitted email.
- Resend invalidates prior outstanding codes and issues a fresh OTP.
- React verification screen now provides six-digit input, verification, and resend behavior.
- Kept legacy token verification support to avoid breaking existing account verification clients.
