# Synthetic registry presentation

Sign in as supervisor, open **Demo Registry**, and click **Load demo records** once.
Upload one PNG from this folder in **New Screening** and select **Permit**.
Extract locally, review every extracted field against the image, then run local checks.
Never change extracted fields just to agree with the database.

| Sample | Expected registry status |
|---|---|
| 01_match | MATCH |
| 02_dob_conflict | CONFLICT on date of birth |
| 03_not_found | NOT_FOUND, not a fraud verdict |
| 04_revoked | REVOKED; escalation required |
| 05_expired | EXPIRED; manual review |
| 06_blocked | BLOCKED; escalation required |
| 07_similar_name | REVIEW_REQUIRED if the printed name variation is retained |
| 08_name_transposition | REVIEW_REQUIRED for AARAV DEOM versus AARAV DEMO |

OCR can misread characters. Correct OCR to what the image actually says, not to the registry.
The overall recommendation also considers image quality and other local checks.
Samples contain no real identity information. Match is not proof of authenticity.
If records have been edited, seed loading does not reset them; inspect their change history.
