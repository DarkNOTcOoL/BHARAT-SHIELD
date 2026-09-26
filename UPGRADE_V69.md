# v6.9 — SIH26188 Demo & Production Hardening

v6.9 does not introduce a new fraud detector. It hardens the complete v6.8 screening stack for repeatable SIH26188 demonstration and local deployment readiness.

- Local preflight/readiness API and CLI.
- Checks supported Python runtime, writable private storage, offline Tesseract assets, YuNet/SFace models, native QR decoder availability, disk capacity, SQLite quick integrity and curated demo sample presence.
- One-click, idempotent seeding of the bundled synthetic Registry, signed-QR, Registry 2.2, visual-template and travel-intelligence demo data.
- Curated SIH26188 demo scenario manifest and authenticated sample preview endpoints.
- Judge-facing Demo Readiness Center on the Command Center/System Status pages.
- Five-minute demonstration runbook.
- Existing screening decisions, risk policy, human review and privacy semantics remain unchanged.
