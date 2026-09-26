# BHARATSHIELD v6.6 — Synthetic Issuer Visual Reference Verification

v6.6 extends Registry 2.0 with a versioned, hash-bound **synthetic visual template feature library**. It does not connect to any real government or issuer template database.

## New capabilities

- `registry2_template_features` links a versioned synthetic issuer template to visual reference features.
- Each feature stores an expected normalized zone, bundled reference asset path, SHA-256, required/critical flag, prototype match threshold and method metadata.
- Local ORB feature matching plus edge-shape agreement checks expected emblem/header/security-pattern regions.
- Missing or moved critical synthetic features generate `ISSUER_VISUAL_FEATURE_REVIEW` and route the case to manual review.
- Visual evidence is stored under `forensic_assist.issuer_visual_security` and can be displayed as an overlay.
- Visual-reference evidence shares the existing forensic-integrity risk family to avoid double-counting with tamper/photo/stamp/layout signals.
- Registry 2.0 events audit the loading of template features.

## Demo

As Supervisor open **Synthetic demo registry** and choose **Load v6.6 visual-template demo**.

Then screen:

- `demo_samples/visual_security/01_template_features_present.png` — expected reference features present.
- `demo_samples/visual_security/02_template_features_missing.png` — critical emblem/header removed.
- `demo_samples/visual_security/03_emblem_moved.png` — critical emblem moved out of the expected zone.

Use Passport metadata for the fictional record `DEMOIND66001 / ANAYA TEMPLATE DEMO` if OCR review needs correction.

## Important limitation

This is **not official issuer authentication**. It only compares against bundled fictional reference assets. It does not validate holograms, UV/IR security features, paper substrate, official seals or government template databases. A clean result does not prove authenticity.
