# BHARATSHIELD Verification Engine v2

## Design

BHARATSHIELD now chooses the verification strategy from the number of supplied documents:

- **1 document:** `SINGLE_DOCUMENT` — document integrity, MRZ, field completeness, issuer/rule checks and a future visual/printing AI layer are prioritized. The system does **not** claim cross-document identity verification.
- **2–4 documents:** `CROSS_DOCUMENT` — shared identity fields and document relationships are compared across uploads. Passport↔visa linking is checked when both are present.

## Evidence model

The AI layer is an observation/extraction source. The local Verification Engine makes deterministic checks:

1. Document type and required-field completeness
2. TD3 MRZ structure/check digits for passports
3. VIZ/MRZ field consistency
4. Country-code validity
5. Trusted reference identity match (synthetic demo records only)
6. Prototype watchlist check (synthetic demo records only)
7. Cross-document consistency when multiple documents are supplied
8. Risk/recommendation calculation

Physical/printing, UV/IR, optical-variable, substrate and other visual security checks are represented as a **pending AI visual-analysis layer** until the Groq integration is added. The engine intentionally does not invent an authenticity result for those checks.

## Source grounding

The design is based on the supplied ICAO Doc 9303 material. Part 2 describes machine-assisted verification, including material, printing and issuing-technique checks and MRZ consistency checks. It also describes layered security rather than dependence on a single feature. Part 4 defines the TD3 passport MRZ field positions and check digits.

## Demo data

The seeded identity and watchlist rows are clearly synthetic. Replace them only with authorized data sources in a production deployment.
