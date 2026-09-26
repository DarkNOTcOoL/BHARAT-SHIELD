# Release notes — BHARATSHIELD v6.7

## Step 11: SIH26188 travel / immigration consistency intelligence

BHARATSHIELD now correlates linked synthetic visa data with Registry 2.2 ENTRY/EXIT history and OCR-visible stamp cues. This directly supports the SIH26188 scenarios around altered visa validity/entries, tampered travel evidence and identity-document screening.

### New backend

- `app/travel_intelligence.py` — deterministic visa/entry chronology and entitlement checks.
- Registry 2.2 evidence exposes richer linked visa metadata.
- `POST /api/registry2/demo-seed-travel-v67` loads fictional conflict histories.
- `TRAVEL_VISA_ENTRY_LIMIT_CONFLICT`, `TRAVEL_STAY_DURATION_EXCEEDED`, visa-date chronology and sequence-review findings.
- Separate explainable `travel_consistency` risk family.
- `travel_intelligence` evidence is saved with each linked screening.
- `travel_immigration_consistency` appears in the screening check matrix.

### Packaged UI

- `dist/v67-travel-intelligence.js` adds a Travel / Immigration Consistency evidence card.
- Registry 2.x page gets a **Load v6.7 travel-intelligence demo** action.
- Three fictional visa/history samples are bundled for clean, entry-limit and duration-of-stay demonstrations.

### Safety / scope

No government, immigration, airline, border-control or official stamp database is connected. The module does not decide admissibility and does not treat missing travel history as fraud. OCR-visible stamps without a synthetic-history match are shown as evidence gaps for manual review.

### Validation

- **150 backend tests passed** across the retained local, registry, recovery and v5.1–v6.7 regression groups.
- The same **2 dense signed-QR fixture assertions** remain environment-limited in this Linux validation environment because native `zxing-cpp` is unavailable here. They are unrelated to v6.7 travel intelligence.
- Dedicated v6.7 tests: **7/7 passed**.
- Packaged v6.7 enhancement JavaScript passes `node --check`.
