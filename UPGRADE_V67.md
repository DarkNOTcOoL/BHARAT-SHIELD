# BHARATSHIELD v6.7 — SIH26188 Travel / Immigration Intelligence

v6.7 is intentionally tied to the SIH26188 fake identity/document-screening scope. It extends the synthetic Registry 2.x identity graph with explainable **visa entitlement vs entry/exit history consistency checks**. It does not connect to any real immigration, airline, border-control or government system.

## New capabilities

- Registry schema metadata advances to **2.2** and exposes richer linked-visa fields (`valid_from`, `expiry`, `number_of_entries`, `duration_of_stay`, passport reference and authority) in screening evidence.
- New `app/travel_intelligence.py` checks the local synthetic travel graph for:
  - entry before visa validity;
  - entry after visa expiry;
  - entry before visa issue;
  - single/double-entry usage beyond the encoded entitlement;
  - duration-of-stay excess using paired ENTRY/EXIT events;
  - future-dated synthetic travel events;
  - visa-issued-after-entry chronology conflicts;
  - incomplete ENTRY/EXIT sequences for officer review.
- OCR-visible lines containing conservative ENTRY/EXIT + date/country cues are compared with synthetic travel events. A missing registry match is treated as an **evidence gap**, never as proof of a fake stamp.
- New explainable `travel_consistency` risk family; only the strongest travel signal contributes points.
- Screening recommendations route positive travel/visa contradictions to manual review while preserving the separate document-authenticity and human-decision layers.
- Screening evidence stores the complete `travel_intelligence` result and a `travel_immigration_consistency` check state.
- Registry 2.2 mutations continue to use the existing tamper-evident audit chain.

## Demo

As Supervisor open **Synthetic demo registry** and choose **Load v6.7 travel-intelligence demo**.

Then screen:

- `demo_samples/travel_intelligence/01_clean_multiple_entry_visa.png` — clean multiple-entry fictional history.
- `demo_samples/travel_intelligence/02_single_entry_overused_visa.png` — a fictional SINGLE-entry visa with two recorded entries.
- `demo_samples/travel_intelligence/03_duration_exceeded_visa.png` — a fictional 7-day stay entitlement with a 19-day recorded stay.

The conflict demo records are:

- `DEMOVISA6701 / KAVYA TRAVEL DEMO`
- `DEMOVISA6702 / OMAR STAY DEMO`

## Important limitation

This is **not a real travel-history or border-admissibility system**. The travel events are synthetic local demonstration records. Missing events can reflect incomplete local history. The module must not infer criminality, immigration status or intent from nationality or travel patterns. It only checks deterministic consistency between encoded visa constraints and the supplied synthetic event history.
