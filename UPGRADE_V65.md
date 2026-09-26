# BHARATSHIELD v6.5 — Synthetic Government Registry 2.0

## What changed
v6.5 upgrades the local synthetic reference database from a document-centric list into a relational identity graph while preserving every legacy `registry_records` row for backward compatibility.

Registry 2.0 adds:
- Identity Master profiles with canonical identity data, aliases, status and versioning.
- One identity linked to multiple document records.
- Explicit document relationships such as Visa → Passport.
- Travel / immigration-stamp event history (synthetic demo only).
- Identity/document alerts including lost/stolen, revoked, blocked, duplicate-identity and review signals.
- Biometric-reference metadata links (the encrypted SFace templates remain in the screening database).
- Versioned issuer/template metadata and expected security-zone labels for future visual checks.
- Registry 2.0 mutation events included in the tamper-evident local registry audit chain.
- Screening-time Registry 2.0 snapshots in evidence, including linked documents, open alerts, recent travel/stamp events and issuer-template references.
- Explainable risk/review integration for synthetic Registry 2.0 alerts.

## Compatibility
The existing document registry is not replaced. Existing v6.4 records are automatically linked to Registry 2.0 identity profiles using exact normalized Name + DOB + Nationality when first initialized or matched. Old signed-QR references and old screening evidence continue to use the legacy record IDs and versions.

## Demo
As Supervisor open **Synthetic demo registry** and select **Load v6.5 Registry 2.0 demo**.

Then use:
- `demo_samples/registry2/01_clean_travel_authorization.png` — clean identity with multiple linked documents and travel/stamp history.
- `demo_samples/registry2/02_lost_stolen_passport_alert.png` — synthetic lost/stolen alert that requires escalation.

All records are fictional. No government, immigration, issuer or watchlist system is connected.

## Upgrade from v6.4
Copy the entire `backend/private` directory from the old installation to the new installation before first start. Do not copy `.venv`.

Use Python 3.12 and install requirements in a fresh virtual environment.
