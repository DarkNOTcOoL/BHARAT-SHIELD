# v5.2 validation record

Performed in the Linux build environment using Python 3.12:

- Backend: `cd backend` then `python -m pytest tests -q` — **73 passed**.
- Frontend: `npm test` — **17 passed** across three test files.
- Production frontend: `npm run build` — successful. Built assets included.
- Seven actual packaged PNG images decoded with the local zxing-cpp engine.
- Signed-valid-but-printed-conflicting and modified-payload-invalid cases both covered.
- Legacy account schema migration preserves accounts and invalidates old sessions; idempotence tested.
- Legacy audit baseline is explicit; repeated initialization does not duplicate events.
- Hash-chain source modification detected; joint tail deletion detected against an older checkpoint.
- Checkpoint signature/fingerprint verification and modified-export rejection tested.
- Encrypted recovery round-trip, wrong password, ciphertext modification, existing-output
  refusal and evidence hash mismatch covered. Restored sessions cleared, source unchanged.
- Existing ten-consecutive-screening test remains passing, along with cancellation and
  stale-response tests. No regression to the stuck Processing state in these interface tests.
- Backend suite denies outbound socket connections. No live government service is connected.

Test warnings: FastAPI/Starlette test-client dependency deprecations. Build warning: main JS
bundle exceeds Vite's advisory chunk-size threshold. Neither prevented successful tests/build.

Limits: frontend tests use jsdom, mocked OCR and mocked requests; they are not full-browser
end-to-end tests. Windows PowerShell, Windows dependency wheels, actual browser camera,
full browser rendering, local OCR recognition accuracy and disconnected-laptop operation
must be validated on the target laptop. No Windows or full-browser pass is claimed here.
The fixture credentials in test files are synthetic test-only values, not default app accounts.

Run this presentation acceptance check on your laptop:

1. Follow UPGRADE_V52.md; verify existing accounts/history/original documents remain readable.
2. Disconnect networking AFTER dependency installation; open the app through 127.0.0.1.
3. Run the seven signed demo cases, reviewing OCR against the visible document each time.
4. Complete ten consecutive screenings, including cancellation, retry and New screening.
5. Confirm officers cannot edit registry records or access supervisor account controls.
6. On disposable test accounts, check password change, disable and session revocation.
7. Download a signed checkpoint and verify it using a separately retained key fingerprint.
8. Stop the server, create an encrypted backup and restore it to a NEW disposable folder.
9. Keep your untouched previous-version folder until you accept the new version.

This is prototype functional validation, not an independent security audit, accuracy study,
biometric evaluation, cryptographic protocol certification or national-security approval.

The release-packaging script excludes all private state, environment folders, credentials,
database files and issuer key files; checks ZIP CRCs and required offline assets; and produces
SHA-256 hashes for the packaged files. These hashes are integrity aids, not a vendor signature.
