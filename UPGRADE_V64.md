# BHARATSHIELD v6.4 — Step 8 Upgrade

## Explainable document layout + security-zone anomaly analysis

v6.4 adds a conservative local geometry layer on top of OCR field boxes, capture evidence and portrait localization.

### New behavior
- Uses OCR field boxes already mapped to the EXIF-normalized original image.
- Applies broad document-family zones rather than one rigid universal template.
- Detects multiple displaced personalized fields.
- Detects strong OCR-field overlap with the AI-localized portrait/photo region.
- Detects substantial collisions between independently extracted field boxes.
- Detects extreme field-position outliers relative to other personalized fields.
- For passports, records a broad lower-page MRZ-band localization aid when MRZ-like text is present.
- Produces a 0–100 **layout anomaly index** that is explicitly **not a forgery probability**.
- Requires either one high-risk security-zone overlap or multiple independent moderate geometry signals before `REVIEW_REQUIRED`.
- Adds `LAYOUT_SECURITY_ZONE_REVIEW` to findings and routes the case to manual review.
- Shares the existing `forensic_integrity` risk family so tamper/photo/stamp/layout evidence is not double counted.
- Adds a **Layout / security zones** visual overlay in the packaged UI.

### Evidence-safety rules
- Too few reliable OCR boxes => `INCONCLUSIVE`; positions are never guessed.
- One isolated broad-zone observation does not by itself create a review alert.
- Officer-corrected text values are not changed by this module.
- This module does **not** authenticate an issuer template, hologram, UV feature or security printing.
- Exact template authentication requires an authorized, versioned reference library for each issuer/document generation.

### Demo samples
`demo_samples/layout_security/01_layout_consistent.png`

`demo_samples/layout_security/02_layout_shifted.png`

Both are fictional and explicitly non-government.
