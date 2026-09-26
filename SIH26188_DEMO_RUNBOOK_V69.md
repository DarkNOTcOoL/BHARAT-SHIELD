# BHARATSHIELD v6.9 — SIH26188 Judge Demo Runbook

All identities, registries, alerts, issuers, travel records and documents in this runbook are fictional/synthetic demonstration data.

## Before the presentation
1. Start BHARATSHIELD locally with Python 3.12.
2. Sign in as Supervisor.
3. Open **Command Center → SIH26188 Demo Hardening → Open Demo Readiness**.
4. Preflight should show **READY** or **READY_WITH_WARNINGS** with no blocking items.
5. Click **Prepare all synthetic demo data** once. The action is idempotent and preserves existing demo records.
6. Keep the demo folder open beside the browser so samples are easy to select.

## Recommended 5-minute flow
1. **Clean active permit** — `demo_samples/video_demo/01_active_match.png` — demonstrate local OCR, synthetic registry match and the Decision Center normal path.
2. **DOB conflict** — `demo_samples/video_demo/03_dob_conflict.png` — show a modified identity-field scenario routing to review with an explainable reason.
3. **Blocked document** — `demo_samples/video_demo/06_blocked.png` — show deterministic CRITICAL / ESCALATE behavior.
4. **Suspicious visa stamp** — `demo_samples/visa_intelligence/03_visa_stamp_suspicious.png` — show local visa/stamp forensic evidence.
5. **Single-entry visa reused** — `demo_samples/travel_intelligence/02_single_entry_overused_visa.png` — show Registry 2.2 travel/visa contradiction.
6. If time remains: **Lost/stolen synthetic alert** or **moved issuer emblem**.

## What to say
- AI/ML: Tesseract LSTM OCR, YuNet face detection and SFace facial representation/comparison.
- Computer vision/forensics: capture quality, tamper anomaly localization, photo/stamp/layout/template visual checks.
- Deterministic corroboration: MRZ/check digits, dates, Ed25519 signed QR, synthetic Registry 2.2 and travel consistency.
- Human-in-the-loop: the system surfaces evidence and an explainable rule risk; the authorized officer records ACCEPT / FLAG / ESCALATE.
- Local-first: sensitive document and biometric processing does not require an external AI API.

## Claims to avoid
Do not claim access to a real government database/watchlist, official issuer-template authentication, certified biometric PAD/liveness, calibrated fraud probability, or automatic legal determination that a document/person is fake.
