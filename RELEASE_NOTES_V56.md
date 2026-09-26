# v5.6 validation and limitations

See `UPGRADE_V56.md` for installation and `DEMO_VIDEO_GUIDE_V56.md` for the nine fictional scenarios and scoring policy.

Validation in the Linux development environment:

- Backend: 92 tests passed, including supervisor-only seeding, preserving existing references, expected scenario scores, expiry deduplication, evidence persistence, and changed reference status changing the outcome. Backend tests block outbound socket connections.
- Frontend: 54 tests passed, including repeated screenings, optional person comparison, supervisor decisions, OCR alternative-read handling and UNASSESSED rendering.
- Actual bundled local English Tesseract execution: all 56 fields across eight clear fictional cards were exact for both original-image and prepared/adaptive paths. The deliberately poor card remained unreadable and resulted in recapture through the screening API. Raw reads and measured OCR timings are included in `OCR_BENCHMARK_V56.json`.

These are automated component/API checks and an actual OCR-engine fixture run. They are not a full Windows/browser/camera acceptance test. No real-ID accuracy, liveness accuracy or trained tamper-detection performance is claimed. The synthetic risk weights are uncalibrated rule points, not a fraud probability. Existing private data is excluded from this release; copy your complete private folder as described in the upgrade guide.
