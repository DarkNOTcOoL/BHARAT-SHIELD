# v5.6 demo video guide

## Preparation

Follow `UPGRADE_V56.md`. Sign in as supervisor and load **v5.6 video demo records** from Demo Registry. Use the images in `demo_samples/video_demo`, select **Permit**, extract locally and compare every extracted field with the original before running checks. Do not copy registry values into the upload to force a match.

All cards and references are fictional. The database demonstrates reference checks such as document status, expiry, field agreement and date consistency. It does not reproduce or claim access to actual government verification policies.

## Expected examples

| Image | Intended observation | Expected rule points |
|---|---|---|
| `01_active_match.png` | Active reference and matching fields | 0 / LOW |
| `02_second_match.png` | A different matching reference | 0 / LOW |
| `03_dob_conflict.png` | Printed DOB differs from reference DOB | 40 / HIGH |
| `04_expired.png` | Expired record and printed expiry | 40 / HIGH |
| `05_revoked.png` | Reference is revoked | 90 / CRITICAL; escalate |
| `06_blocked.png` | Reference is blocked | 100 / CRITICAL; escalate |
| `07_unknown_record.png` | No reference record | UNASSESSED; review |
| `08_similar_name.png` | Similar spelling, not exact equality | 10 / REVIEW |
| `09_poor_capture.png` | Deliberately unreadable image | UNASSESSED; recapture |

The first eight expected scores assume correctly read/reviewed fields, unchanged reference records and no additional conflicting history. The last example is deliberately degraded: do not fill unreadable values using the reference. Its registry result can be NOT_CHECKED/NOT_FOUND when OCR cannot extract a lookup key, while the overall outcome remains recapture/unassessed. The manifest's MATCH for this case applies only when all printed fields are supplied as a controlled rule test.

The seed button never overwrites records. If you already edited these references, inspect their versions and edit with an audit reason or use a separate demo installation. Do not delete real evidence to obtain a preferred result. Date checks use the current date; the active samples expire on 2035-12-31. These permits have no portrait, so optional face comparison should be inconclusive; skip it for this demonstration.

## Suggested 3–4 minute sequence

1. Explain: "This prototype processes documents locally and compares them with a fictional reference database. It supports an officer's review; it does not certify authenticity."
2. Show the reference record and its ACTIVE status. Screen `01_active_match.png`. Show extracted fields, registry MATCH and 0 rule points. Say "No inconsistency detected in the checks performed."
3. Screen `03_dob_conflict.png`. Show the printed DOB, differing reference DOB, and the 40-point identity-field factor.
4. Screen `05_revoked.png`. Show the reference's REVOKED status, 90 points and escalation. This demonstrates that matching text alone is insufficient.
5. Screen `07_unknown_record.png`. Show UNASSESSED: absence from this database is not proof that a document is fake.
6. Screen `09_poor_capture.png`. Show the recapture recommendation. Unreadable input must not receive a clean pass.
7. Open a saved screening and its evidence export. Show the policy version, factors, gaps and independent officer decision.

Optional: as supervisor, change the first reference's status to REVOKED with an audit reason, screen the same file again and show the changed result. Restore the reference afterward with another reason. This demonstrates live rule evaluation rather than a filename-based preset.

## How points work

Prototype policy `SYNTHETIC_REFERENCE_RISK_V1` adds the largest factor in each rule family, then caps the sum at 100. For example, printed expiry and reference expiry are both in the expiry family and do not double-count.

| Rule family | Points |
|---|---:|
| Blocked reference / revoked reference | 100 / 90 |
| Printed/reference field conflict | 40 |
| Expiry | 40 |
| Similar name requiring review | 10 |
| Inconsistent or future dates | 35 |
| Supported document-number format failure | 15 |
| Conflicting identity in local history | 35 |
| Cross-document conflict | 40 |
| Invalid MRZ checks | 30 |
| Invalid configured synthetic signature or signed-data conflict | 45 |

Bands: 0 LOW; 1–29 REVIEW; 30–69 HIGH; 70–100 CRITICAL. If there are zero observed points but unresolved evidence, the score is UNASSESSED rather than zero. If a conflict exists alongside missing evidence, its points remain visible and the evidence status is INCOMPLETE. Optional face comparison is not folded into these document-rule points.

These weights are prototype choices, not a probability of fraud, measured detection accuracy or government policy. An expired document is not necessarily forged. A field conflict can come from OCR or stale reference data. Human review and acceptance remain separate.

## Measurement evidence

`OCR_BENCHMARK_V56.json` contains actual local Tesseract reads and timings for all nine cards. The eight clear cards yielded 56/56 exact fields for both the original-image and prepared/adaptive paths. The poor card yielded 0/7 fields and triggered a retry without obtaining a usable extraction. This demonstrates correct handling of these samples, not an increase in measured accuracy over the original-image path or accuracy on real IDs.

The report compares the same current engine/parser on original versus prepared/adaptive inputs, not separate v5.5 and v5.6 installations. Timings exclude worker startup, Python preparation and UI, use sequential runs, and may reflect warm-cache effects. Consult the JSON for actual timings; do not present them as an end-to-end speed guarantee.
