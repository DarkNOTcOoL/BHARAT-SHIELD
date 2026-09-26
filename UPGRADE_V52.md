# BHARATSHIELD Local v5.2 — upgrade your working installation

This is a local SIH demonstration prototype, not a certified national-security system.
No government service, cloud OCR, external inference or online issuer lookup is used at runtime.
The browser still calls your own backend on 127.0.0.1; a local API is not a cloud dependency.

## 1. Preserve your working version

1. Stop your current backend using Ctrl+C.
2. Keep the entire working v5.1 folder unchanged as your rollback copy.
3. Extract this ZIP into a NEW folder. Do not extract over your working installation.
4. COPY the complete CURRENT `BHARATSHIELD/backend/private` folder into the new
   `BHARATSHIELD/backend` folder. Include every database, `document.key`, and `documents`.
   Do not use an older v4 private folder. Do not copy only individual database files.
5. If you already started the new version and it has private data, stop. Do not merge or
   overwrite either private folder; preserve both and decide which dataset to keep.
6. For this v5.1-to-v5.2 upgrade, retain the NEW bundled `backend/trust` directory.
   Subsequent upgrades must also preserve any custom public trust keys and external issuer keys.

The package intentionally contains no private folder, account database, password, document
encryption key, or issuer private signing key. The bundled QR samples have a public verification
key only; their temporary signing key was not saved. Existing accounts work after migration,
but existing login sessions are invalidated. Sign in again.

## 2. Exact PowerShell commands

Open PowerShell in the NEW `BHARATSHIELD` folder. Run each line separately:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use Python 3.12, 64-bit. The setup requires package downloads; routine screening does not.
Open http://127.0.0.1:8000 and use your existing username/password. Do not recreate an
account already copied. Node/npm is not required to run the packaged frontend.
If the page looks old, press Ctrl+F5 once. Do not run both versions on port 8000.

If PowerShell was closed, open it in the new backend folder and run only:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For a genuinely fresh installation only, create an account before starting:

```powershell
.\.venv\Scripts\python.exe manage_users.py --username SNEH --name "Sneh" --role supervisor
```

## 3. First signed-QR test

1. Sign in as supervisor.
2. Open Demo Registry and click **Load signed QR demo records**. Existing records are
   never overwritten. These samples reference version 1 of REG-DEMO52-001 and 002.
3. New Screening → upload `demo_samples/signed_qr/01_signed_match.png` → choose Permit.
4. Extract text locally. Review the visible fields; OCR can misread letters/digits.
5. Expected values: AARAV DEMO; DEMO5201; DOB 2001-03-14; nationality IND;
   issuing country IND; issue date 2024-01-01; expiry 2035-12-31. Optional fields are blank.
6. Run local checks. Inspect **Signed demo QR — local verification**.
7. Expected: SIGNATURE_VALID plus CONSISTENT, assuming the reviewed fields and reference
   are unchanged. This is not a government verification or authenticity certificate.
8. Click New screening and repeat with the remaining samples. Do NOT correct intentionally
   changed printed data to match the registry; review OCR against what the image actually says.

| Sample | Signature result | Expected comparison / purpose |
| --- | --- | --- |
| 01_signed_match.png | SIGNATURE_VALID | CONSISTENT if reviewed fields match |
| 02_printed_dob_changed.png | SIGNATURE_VALID | SIGNED_DATA_CONFLICT: printed DOB is 2002-03-14 |
| 03_payload_tampered.png | SIGNATURE_INVALID | UNVERIFIED; review required |
| 04_unknown_issuer.png | UNKNOWN_DEMO_ISSUER | UNVERIFIED; review required |
| 05_unsigned_required.png | NO_SIGNED_QR | Required signed QR not verified; review |
| 06_substituted_valid_qr.png | SIGNATURE_VALID | SIGNED_DATA_CONFLICT: another record's valid QR |
| 07_reused_credential.png | SIGNATURE_VALID | CONSISTENT data; history signal after sample 01 |

Image quality or missing reviewed fields can additionally require recapture/review. Editing
the reference increments its version and can produce REFERENCE_VERSION_CHANGED/PARTIAL.
Reloading demo records does not reset edited records. To demonstrate pristine samples again,
use a separate fresh installation; do not delete working history.

## 4. What v5.2 adds

- Locally decoded, Ed25519-signed synthetic BS52 QR credentials; explicit unknown/disabled/
  invalid/malformed/multiple-QR states. QR URLs are never fetched.
- Reviewed OCR vs verified signed fields vs versioned synthetic registry comparisons,
  preserved in evidence JSON and the self-contained HTML report.
- Supervisor-editable requirement for a signed demo QR on a reference record.
- Bounded local-history investigation signals: exact image rescan, same document key with
  changed name/DOB, same name/DOB with another number, and reused signed credential IDs.
  Latest 1000 screenings searched; at most 50 candidates displayed. No face-history search.
- Separate hash chains for screening audit, registry history and security events; signed
  audit checkpoints downloadable by supervisors in Settings.
- Settings: password change; supervisor account enable/disable, password reset, session
  listing/revocation, latest 100 security events, integrity checks. CLI account creation remains.
- Session expiry: 15 minutes without authenticated API requests, absolute maximum eight
  hours. Background requests count as activity. Password changes/reset revoke all sessions.
- Per-document local processing timing. It excludes browser OCR, human review and database
  commit, and is NOT an end-to-end passenger throughput benchmark.
- Offline password-encrypted recovery utility, with evidence validation and new-folder-only
  restore. See RECOVERY_V52.md.

## 5. Audit checkpoint procedure

Settings → Check audit integrity → Download signed audit checkpoint. Keep the JSON and its
`public_key_sha256` fingerprint separately from the machine being checked. An independently
retained fingerprint is necessary; trusting a fingerprint from a newly supplied file alone
does not establish its origin. The audit signing key is a LOCAL application key, separate from
all issuer signing keys, stored under private and protected by OS permissions (not encrypted).

After stopping the server, verify a saved checkpoint from the backend directory:

```powershell
.\.venv\Scripts\python.exe verify_audit_checkpoint.py --file "C:\path\audit-checkpoint.json" --sha256 "PASTE_PREVIOUSLY_RETAINED_FINGERPRINT"
```

Older events are baselined at upgrade, not retrospectively authenticated. Checkpoints cover
audit events, not every database field or document. Document hashes are checked separately
when exporting evidence and during recovery validation. Each database is checked separately;
the export is not a cross-database atomic snapshot. Tail deletion requires an older externally
retained checkpoint. A local administrator who controls both databases and keys can rewrite
local history; these are tamper-evident checks, not immutable storage or a blockchain.

## 6. Separate demo issuer

The optional issuer tool creates fictional Permit images only. It cannot issue government
credentials. Keys must be outside the BHARATSHIELD application tree; for better separation,
run it on another offline issuer workstation. A folder on the same machine is not a strong
security boundary against its administrator.

1. Add a fictional Permit in Demo Registry. Supply ISO DOB, issue and expiry dates.
   For this fixed demo image layout, leave gender, issuing authority and passport reference
   blank; use a name up to 30 characters and a document number up to 24 characters.
2. Enable Require signed demo QR before saving; download its reference JSON from View record.
3. From backend, initialize a new password-encrypted issuer key outside the application:

```powershell
.\.venv\Scripts\python.exe ..\DEMO_ISSUER\issuer.py init --key-dir "C:\BharatShieldDemoIssuer"
```

4. Import only `trust-public.json`, checking the fingerprint shown by the issuer independently:

```powershell
.\.venv\Scripts\python.exe import_demo_trust.py --file "C:\BharatShieldDemoIssuer\trust-public.json" --sha256 "PASTE_ISSUER_FINGERPRINT"
```

5. Issue the fictional document using the downloaded record JSON:

```powershell
.\.venv\Scripts\python.exe ..\DEMO_ISSUER\issuer.py issue --key-dir "C:\BharatShieldDemoIssuer" --record "C:\path\REG-record.json" --out "C:\path\new-demo-permit.png"
```

Use unique key IDs for separate issuers. Never transfer issuer-private.pem into the backend,
publish it, or share its password. Do not regenerate the packaged demo trust key, as existing
sample signatures depend on it. The sample generator refuses to overwrite an existing trust file.

## 7. Scope, validation and next phase

Implemented tests cover actual PNG QR decoding, three-source conflicts, unknown/tampered QR,
required-QR absence, permissions, seed idempotence, reference version drift, duplicate signals,
audit tampering/tail deletion against a checkpoint, signed exports, password/session lifecycle,
and encrypted restore. Existing OCR lifecycle tests include ten consecutive screenings.
Backend tests deny outbound socket connections. Frontend tests use jsdom and mocked OCR/network.
Production frontend builds, but full-browser rendering/camera and native Windows execution
have NOT been validated in this environment. Test these on your presentation laptop offline.

Deferred: two-person acceptance policy; dedicated keyboard-driven checkpoint dashboard and
daily latency analytics; biometric cross-identity history search; calibrated tamper/stamp
models; liveness; chip authentication; authorized government integration. They are not claimed
as implemented. Existing one-supervisor, version-checked review resolution is retained.

A valid QR does not bind a photo or prove the presenter's identity; exact credential copying
remains possible. Registry and signed fields are not statistically independent evidence.
No probability of genuineness or national-security readiness is claimed. Metadata remains
plaintext SQLite; protect the machine, private directory, exports, recovery passwords and
issuer keys with OS access controls and disk encryption. Loopback hosting is not an air gap.

Rollback: stop v5.2 and reopen the untouched original installation. Do not copy a migrated
v5.2 private directory back into an older version. New v5.2 screenings are not present in
the original copy; preserve both if rolling back.
