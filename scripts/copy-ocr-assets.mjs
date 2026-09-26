import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.dirname(scriptDir);
const nodeModules = path.join(projectRoot, 'node_modules');
const publicDir = path.join(projectRoot, 'public', 'ocr');
const coreDest = path.join(publicDir, 'core');
const tessdataDest = path.join(publicDir, 'tessdata');
const workerDest = path.join(publicDir, 'worker.min.js');

function mustExist(p, label) {
  if (!fs.existsSync(p)) throw new Error(`OCR asset missing: ${label} (${p})`);
}

fs.rmSync(publicDir, { recursive: true, force: true });
fs.mkdirSync(coreDest, { recursive: true });
fs.mkdirSync(tessdataDest, { recursive: true });

const tesseractPkg = path.join(nodeModules, 'tesseract.js');
const corePkg = path.join(nodeModules, 'tesseract.js-core');
const engPkg = path.join(nodeModules, '@tesseract.js-data', 'eng');

const worker = path.join(tesseractPkg, 'dist', 'worker.min.js');
mustExist(worker, 'tesseract.js worker');
fs.copyFileSync(worker, workerDest);

for (const file of fs.readdirSync(corePkg)) {
  if (file.endsWith('.js') && file.startsWith('tesseract-core')) {
    fs.copyFileSync(path.join(corePkg, file), path.join(coreDest, file));
  }
}

const candidates = [
  path.join(engPkg, '4.0.0_best_int', 'eng.traineddata.gz'),
  path.join(engPkg, '4.0.0', 'eng.traineddata.gz')
];
const trained = candidates.find(fs.existsSync);
mustExist(trained, 'English traineddata');
fs.copyFileSync(trained, path.join(tessdataDest, 'eng.traineddata.gz'));

console.log('BHARATSHIELD: local OCR assets prepared.');
