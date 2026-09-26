# BHARATSHIELD v7.0 release notes

## Delivered

- One reproducible React frontend replaces the base app plus twelve runtime enhancement scripts.
- Existing theme, sidebar and base stylesheet retained. New sections reuse the existing palette and panels.
- Shared saved screening evidence powers the Decision Center and detailed panels, removing per-panel screening fetches.
- Recommendation, risk points, check coverage and priority reasons appear at the top of results.
- Expandable evidence sections defer inspection images until needed. The optional camera/liveness section unmounts when closed.
- Native React registry identity search, linked-document/travel/alert administration, issuer/travel demo seeding and demo readiness.
- Abortable read requests, stale-response protection, explicit errors and local evidence-section recovery.
- Person-check completion refreshes saved evidence. Original report/export and review/acceptance workflows retained.
- Build/package checks require the integrated components and reject the retired runtime scripts.

## Validation performed

- 165 backend tests passed, without excluding the two dense-QR cases previously documented as environment-limited. Native zxing-cpp was installed for this run.
- 67 frontend tests passed, including ten consecutive screening resets, cancellation, original/QR OCR disagreement, person/liveness components, review decisions, lazy sections, stale requests, permission-aware controls and audited registry linkage.
- Vite production build passed. It emits one application entry script. The bundle-size advisory remains; it does not indicate a build failure.
- The application source contains no MutationObserver enhancement loop. Served output contains no standalone v5.x/v6.x enhancement scripts.
- Backend application comparison against v6.9 FULL_FIXED shows only release/version-description changes in main.py. Detection modules, risk weights and storage schemas are unchanged.
- Backend tests use temporary data directories and block outbound sockets. No user private folder or review-session credentials are included in the release.

The tests ran on Linux with Python 3.12, including FastAPI TestClient and jsdom component tests. Browser automation failed to start in this execution environment; no full visual browser, live-camera or Windows acceptance pass is claimed. Do the Windows rehearsal in UPGRADE_V70.md and keep the prior working folder until it passes.

## Scope and limits

This release addresses frontend maintainability and evidence presentation. It does not establish improved real-ID extraction accuracy, forensic false-positive rates or an end-to-end speed benchmark. Structural work is reduced by removing duplicate result fetches and deferring hidden views, but no measured speedup is claimed.

The existing local OCR fallback, forensic assistance, active head-turn challenge, face-template history and synthetic registry remain prototype capabilities. No real government/issuer/watchlist source is connected. Liveness is not certified PAD. Rule points are not a calibrated fraud probability, and a clean result is not proof of authenticity.

No new database migration is required by this frontend release. Preserve your complete private folder and customized issuer trust settings as described in UPGRADE_V70.md.
