# BHARATSHIELD v5.9 release notes

## Step 3 — stronger person verification

- Added `RANDOMIZED_ACTIVE_HEAD_TURN_V1` active-liveness workflow.
- Added short-lived one-time server-issued challenge IDs.
- Added YuNet facial-landmark head-turn measurements from three live-camera frames.
- Added quality rejection for blur, exposure, small face and excessive roll during liveness.
- Added quality-gated person capture before SFace similarity evidence is recorded.
- Added liveness evidence/history, SHA-256 frame hashes, model hash, officer attribution and audit event.
- Challenge frames are not persisted by the backend.
- Person evidence remains separate from document-authenticity risk scoring.
- SFace similarity remains `REVIEW_ONLY_UNCALIBRATED`; no operational MATCH/NO-MATCH probability is claimed.
- Active liveness is explicitly labelled prototype replay resistance, not certified PAD.
- Added a prebuilt-frontend enhancement script so the packaged release does not require npm at runtime.

## Regression intent

v5.8 tamper/photo-integrity evidence, signed QR, registry comparison, manual review, audit chaining, encrypted originals, recovery and repeated-screening behavior remain unchanged except where v5.9 explicitly replaces `liveness: NOT_IMPLEMENTED` with the optional active-challenge states.
