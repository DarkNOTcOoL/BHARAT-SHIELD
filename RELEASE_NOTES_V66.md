# Release notes — BHARATSHIELD v6.6

## Step 10: issuer template + visual security-feature references

BHARATSHIELD now combines its broad v6.4 layout/security-zone analysis with a separate v6.6 **versioned synthetic reference-feature matcher** backed by Registry 2.0/2.1 metadata.

### New backend

- `app/visual_security.py` — local ORB + edge-shape matching inside expected feature zones.
- `registry2_template_features` — hash-bound reference feature metadata.
- Registry 2.1 profile lookup by document type, issuer country, issuer name and issue date.
- `POST /api/registry2/demo-seed-visual-v66`.
- `GET /api/registry2/issuer-templates/{template_id}/features`.
- `GET /api/screening/{id}/image?view=visual-security` overlay.
- `ISSUER_VISUAL_FEATURE_REVIEW` finding and explainable forensic risk integration.

### Bundled fictional visual references

- Synthetic issuer emblem.
- Synthetic passport header band.
- Synthetic security rosette.
- Clean, missing-feature and moved-feature fictional passport demonstrations.

### Safety / scope

Only bundled synthetic reference features are matched. No authorized issuer, government, passport, immigration or watchlist template service is connected. The anomaly index is not a forgery probability. Hologram, UV, IR and substrate authentication remain outside the prototype.

### Validation

- 143 backend tests passed across the retained v5.x/v6.x regression groups.
- 2 dense signed-QR fixture assertions were excluded in this Linux validation environment because native `zxing-cpp` is unavailable here; Windows Python 3.12 installs the dependency from `requirements.txt`.
- v6.6 clean/missing/moved synthetic reference-feature tests passed.
- Packaged enhancement JavaScript passes `node --check`.

