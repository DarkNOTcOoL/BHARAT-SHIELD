# BHARATSHIELD Local v5.3 — OCR intake and forensic assist

This version addresses the reported `DEMO5201PLFAK` extraction problem without a preset ID.
It remains a local demonstration prototype. It does not authenticate government IDs.

## What changed

- OCR requests word/line bounding boxes and separates distant text geometrically.
- Label extraction is line-based. Text from adjacent QR regions is not blindly joined to an ID.
- Identifier letters/digits are preserved, including O/0. A contiguous suspicious suffix is
  NOT silently deleted. Ambiguous multi-token identifiers are retained for review unless
  a layout boundary separates the extra text. No registry or signed QR identity value is
  used to fill OCR fields.
- Optional local preparation locates/masks QR pixels on a WORKING COPY, applies EXIF
  orientation, bounds its longest side to 2600 pixels, and uses grayscale/autocontrast.
- When QR regions are found, original-colour and prepared working-copy OCR are compared.
  Original-image suggestions are retained; disagreements are displayed explicitly.
  Higher OCR confidence is not assumed to mean a correct identifier.
- The review screen displays preparation preview, source strings, warnings and capture advice.
  Raw engine text, proposed fields, alternate read, and officer corrections are retained in
  evidence. Intake notes are browser-supplied, not independently attested.
- Three experimental forensic views: texture-energy heatmap, repeated-feature candidate
  pairs, and JPEG recompression residual. Results and limitations appear in saved reports.
- OCR/preparation/forensic phase timings are visible in evidence. Work sizes are bounded;
  one OCR worker is reused within a batch. QR dual reading adds work: no universal speedup
  or production throughput claim is made.

## Important scope limits

There is NO trained, validated tamper classifier. Texture edges and repeating print may be
normal; repeated-feature candidates do not prove copy-move editing. A clean-looking image
does not prove genuineness. These aids do not automatically reject a person or clear a
document. Signed-field/registry/MRZ conflicts remain separate rule-based evidence.

Boundary and highlight checks give heuristic guidance. Automatic document cropping,
perspective correction, reliable glare segmentation, font/stamp classification, resampling
detection and additional language OCR are NOT implemented. The English OCR pipeline works
with uploaded real-document images, but there is no guarantee across all layouts, scripts,
security backgrounds, cameras or image quality. Missing fields stay missing for review.

## Upgrade safely

1. Stop v5.2 with Ctrl+C. Keep its entire folder unchanged.
2. Extract this ZIP into a NEW v5.3 folder, not over an old installation.
3. Copy the COMPLETE current `backend/private` folder into the NEW backend directory.
   Never merge two private folders or copy only selected databases/key files.
4. If you used the bundled v5.2 public trust configuration unchanged, the new bundled
   `backend/trust` already contains the same public key. If you imported custom issuer
   keys or disabled keys in v5.2, carry over that complete current trust directory too.
   Do not re-enable a deliberately disabled key by replacing it with package defaults.
5. Keep separate issuer private keys outside the application. Do not copy them into backend.
6. Open PowerShell in the NEW BHARATSHIELD folder and run each line:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use Python 3.12 64-bit. Setup downloads dependencies; routine operation is local.
Open http://127.0.0.1:8000 and sign in with the existing account. Do not recreate it.
Press Ctrl+F5 if the old interface is cached. Node/npm is not needed to run this package.

## Test the reported OCR issue

1. Supervisor → Demo Registry → Load signed QR demo records if not already loaded.
2. New Screening → `demo_samples/signed_qr/01_signed_match.png` → Permit.
3. Keep Prepare OCR locally enabled and click Extract text locally.
4. Inspect Document number, the raw OCR, source values and any original/prepared disagreement.
5. The real engine test here extracted `DEMO5201` from the original using word geometry,
   even though its raw OCR contained `. pL Fak` beside the number. This was NOT a preset.
6. The prepared read in testing produced `DEM0O5201`; the app therefore keeps the original
   suggestion and shows the disagreement. Do not use a registry value to force agreement.
7. Review all visible fields. Click Run local checks; check signed comparison separately
   from OCR quality. Low OCR confidence or history conflicts can still require review even
   if SIGNATURE_VALID and CONSISTENT are displayed.
8. If masking hides printed text, untick Prepare OCR locally and extract again. The original
   image is retained unchanged. Cancelling clears the form; history already saved remains.
9. Repeat with your own locally held document. You do not need to upload your original ID to
   this chat. Missing authorized reference data must remain unverified—not automatically fake.

## Inspect possible tampering

After screening, open Experimental tamper-inspection aids:

- Texture heatmap: high-frequency image energy, including normal print and edges.
- Repeated-feature candidates: red lines connect similar features with a common displacement.
  Text, QR patterns, backgrounds and security printing can trigger them.
- JPEG residual: differences after recompression; not proof of digital alteration.

`MANUAL_INSPECTION_REQUIRED` indicates repeat candidates, not a fraud verdict.
`NO_REPEAT_INDICATOR_FOUND` means only that this particular repeat heuristic found none.
Authenticity remains `NOT_DETERMINED`. Human review and authorized references are required.

## Validation and rollback

See VALIDATION_V53.md. Windows and full-browser/camera operation still need testing on your
laptop. First test locally with fictional samples, then test offline after installation.
Keep real IDs, exports and backups private. Original documents are encrypted, but metadata
remains plaintext SQLite and requires OS permissions/disk encryption.

To roll back, stop v5.3 and use the untouched old installation. Do not copy the new private
directory back into an older version. New v5.3 screenings will exist only in the v5.3 copy.
The v5.2 account, audit and recovery instructions still apply; use the matching application
version when restoring. Keep backups of custom public trust settings and external issuer keys.
