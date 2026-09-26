# v5.5 — Optional person comparison and decision workflow

## Delivered changes

- Explicit opt-in on each screening; no automatic camera access or inference.
- Live camera capture without audio, readiness gating, preview before submission, retake,
  close, permission-error retry and stream cleanup on departure or late permission response.
- Clearly labelled uploaded-photo alternative. Source labels are browser-reported, not attested.
- Explicit SKIPPED result, separate from NOT_RUN, INCONCLUSIVE, MODEL_ERROR and REVIEW_REQUIRED.
- One-document / one-capture local YuNet + SFace comparison. Ambiguous/small faces return
  an explanation. No calibrated identity threshold or liveness model was added.
- Results include actor, server time, capture source, image hash, and model/face geometry
  where inference succeeds. Last 30 attempts are retained in evidence with an attempt count;
  audit events retain each saved attempt's status, source and capture hash.
- Camera images and embeddings are not persisted by the server. Original document storage
  retains the existing encryption. Camera preview URLs are revoked after clear/unmount.
- New document coverage excludes optional face/liveness checks. Running/skipping comparison
  does not modify document recommendation, coverage, risk or final decision. Older saved
  coverage is retained. SKIPPED cannot erase a completed or inconclusive comparison.
- Final accepted/resolved cases reject new person evidence until reopening/new screening.
- Supervisor ACCEPT on queued cases now opens the existing versioned claim/resolve workflow
  directly in the result page. Officer routing, short reasons, stale versions and blocked or
  revoked records remain subject to server authorization and validation.
- Saved decision and comparison state propagate to the active document within a batch.

## Validation executed

- 88 backend tests passed. New tests cover optional skip, attribution, capture source,
  image hashing, result history, absence of new photo/embedding files, unchanged decisions
  and coverage, successful ordinary acceptance after skip, and supervisor role/reason/version
  guards. Existing auth, blocked-record, encryption, OCR, QR and review tests also pass.
- 50 frontend tests passed. New tests cover opt-in, skip, pre-send preview, uploaded source,
  cancellation/late response, backend errors, denied camera permission, camera cleanup,
  mocked video-to-blob capture, supervisor claim/accept, ordinary acceptance and stale review.
- Production frontend build completed with the bundled offline OCR runtime.
- Both bundled face-model SHA-256 hashes match their model manifest.
- Actual SFace inference on a synthetic tensor produced finite output; the existing actual
  YuNet blank-image test returned inconclusive. The positive comparison/geometry unit test
  uses mocked model outputs. These checks establish loading/flow, NOT face-match accuracy.

## Testing limits

No physical webcam, full Windows browser or real-ID/person dataset was exercised here.
The front-end camera tests use mocked browser APIs. Follow UPGRADE_V55.md on the actual laptop
to test permissions, rendering, capture quality, retakes and disconnected operation.
There is no measured false-match/false-non-match rate, demographic assessment, liveness
validation or operational threshold. A virtual camera, photograph or screen replay can defeat
still-image capture. Cosine similarity is not identity probability or an authenticity score.

No new runtime dependency or cloud API was added. Setup still downloads dependencies.
Dependency deprecation warnings and the pre-existing large JavaScript bundle warning remain;
they did not fail the tests or build. Broad version ranges in requirements remain unchanged.

## Reproduction

```text
cd backend
python -m pip install -r requirements.txt pytest httpx
python -m pytest -q
cd ..
npm ci
npm test
npm run build
python scripts/package-release.py --out <new-absolute-zip-outside-project>
python scripts/verify-release.py <new-absolute-zip-outside-project>
```

Packaging excludes private state, keys, databases, environments and node_modules. The ZIP
contains the compiled frontend, local models, English OCR, upgrade guide and SHA-256 manifest.
