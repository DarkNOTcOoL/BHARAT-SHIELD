# BHARATSHIELD v6.3 — Advanced Capture Intelligence + Multi-Preprocessing OCR

## Upgrade safely
1. Keep the complete working v6.2 folder as a backup.
2. Extract v6.3 into a new folder.
3. Copy the complete `backend/private` folder from v6.2 into the new v6.3 `backend` folder. Keep all keys/databases together.
4. Use Python 3.12, create a fresh `.venv`, install requirements, then start Uvicorn as before.

## New in v6.3
- Server-recomputed local capture intelligence for document boundary, glare-like saturation, uneven lighting, text-line skew and orientation guidance.
- Three same-geometry OCR preprocessing variants: CLAHE + sharpen, illumination normalization, and adaptive binary.
- The packaged frontend automatically retries local Tesseract on up to two alternate variants when the first read is weak and records which read was selected.
- Same-geometry policy keeps OCR field boxes aligned to the EXIF-normalized original evidence frame.
- Perspective correction remains a preview only; rotation/deskew remains guidance only. No silent crop/rotation changes the evidence frame.
- Strong glare can route a screening to RECAPTURE. Skew/shadow are advisory findings.
- Capture/OCR strategy is saved in evidence and shown in the packaged UI.

## Demo samples
Use `demo_samples/ocr_capture/01_shadow_low_contrast.png` to show the fallback OCR path and `02_glare_recapture.png` to show capture-quality recapture guidance. Both are fictional presentation samples.

## Important limitations
Preprocessing improves readability; it does not prove authenticity. OCR still depends on camera quality, fonts, languages and document design. This release bundles English OCR only. Perspective/rotation correction is deliberately not silently applied because doing so would require trustworthy geometry remapping for every evidence overlay.
