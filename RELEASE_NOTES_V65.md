# Release notes — BHARATSHIELD v6.5

## Registry 2.0
The main addition is a relational synthetic reference layer that models identities, linked documents, document relationships, travel/stamp events, alerts, biometric references and issuer/template metadata. It remains local SQLite demo data and is never represented as a real government source.

## Screening integration
A normal exact registry match now attempts to attach its Registry 2.0 identity graph. Open synthetic alerts are added to the screening evidence. Lost/stolen, revoked or blocked document alerts require escalation. Review/duplicate/watchlist-review demo alerts require human investigation. The old external watchlist remains `NOT_CONNECTED`.

## Privacy and audit
Registry 2.0 stores biometric reference metadata only, not raw live-camera images. Existing encrypted biometric templates remain in `bharatshield.db`. Registry 2.0 mutations are appended to the local hash-chained registry audit trail.

## Validation
Dedicated Registry 2.0 tests cover permissions, idempotent demo seeding, linked identity graphs, clean reference enrichment, lost/stolen escalation, risk integration, travel/alert administration, screening recommendation integration and audit-chain integrity.

Existing v5.x–v6.4 regression groups remain compatible. The two previously documented dense signed-QR fixture cases still depend on native `zxing-cpp` in the validation environment and are unrelated to Registry 2.0.

## Limitations
This is synthetic local demonstration infrastructure. It does not connect to government identity, immigration, passport, visa, police, issuer or watchlist systems. Travel history and alerts are fictional demo records. Issuer/template metadata is not official template authentication.
