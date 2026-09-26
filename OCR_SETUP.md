# Local OCR

English worker, WASM wrappers and trained data are bundled in dist/ocr and public/ocr.
No CDN is needed during screening. npm ci refreshes the development copies; npm run build copies them into dist.
OCR runs in the browser on the original capture. Officers review extracted fields before rule checks.
