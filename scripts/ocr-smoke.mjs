// Run real bundled English OCR; no remote model or issuer lookup.
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createWorker} from 'tesseract.js';
import {parseStructuredOCR} from '../src/ocrParser.js';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const worker=await createWorker('eng',1,{workerPath:path.join(root,'node_modules/tesseract.js/src/worker-script/node/index.js'),corePath:path.join(root,'dist/ocr/core'),langPath:path.join(root,'dist/ocr/tessdata'),gzip:true,cacheMethod:'none'});
try{
 for(const input of process.argv.slice(2)){
   const started=Date.now();const {data}=await worker.recognize(input,{}, {text:true,blocks:true});
   const parsed=parseStructuredOCR(data,'Permit');
   console.log(JSON.stringify({file:path.basename(input),elapsed_ms:Date.now()-started,confidence:data.confidence,raw_text:data.text,...parsed}));
 }
}finally{await worker.terminate();}
