# BHARATSHIELD OCR setup

This build self-hosts the Tesseract.js worker, Tesseract.js core files, and English traineddata under `/ocr` so the browser does not need to fetch OCR runtime assets from a CDN.

After extracting the project:

```powershell
npm install
npm run dev
```

`npm install` runs `scripts/copy-ocr-assets.mjs` automatically and prepares `public/ocr/`.

The OCR engine is still Tesseract.js running locally in the browser; no document image is sent to a third-party OCR service.
