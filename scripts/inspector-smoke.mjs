// Real bundled engine smoke check on synthetic PNGs only; not a real-ID benchmark.
import path from 'node:path';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {createWorker} from 'tesseract.js';
import {parseStructuredOCR} from '../src/ocrParser.js';
import {fieldGeometry,serializeNotes} from '../src/fieldGeometry.js';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const worker=await createWorker('eng',1,{workerPath:path.join(root,'node_modules/tesseract.js/src/worker-script/node/index.js'),corePath:path.join(root,'dist/ocr/core'),langPath:path.join(root,'dist/ocr/tessdata'),gzip:true,cacheMethod:'none'});
try{
 for(const file of process.argv.slice(2)){
  const bytes=fs.readFileSync(file);assert.equal(bytes.subarray(1,4).toString(),'PNG');
  const dimensions=[bytes.readUInt32BE(16),bytes.readUInt32BE(20)];
  const started=Date.now(),{data}=await worker.recognize(file,{}, {text:true,blocks:true});
  const parsed=parseStructuredOCR(data,'Permit'),boxes=fieldGeometry(data,parsed.notes.source_values,dimensions);
  const box=boxes.find(b=>b.field==='documentNumber');assert.ok(box,'Document-number box must come from actual engine geometry');
  assert.equal(box.text.toUpperCase(),parsed.fields.documentNumber);
  assert.ok(JSON.parse(serializeNotes({...parsed.notes,field_boxes:boxes})).field_boxes.length);
  console.log(JSON.stringify({file:path.basename(file),milliseconds:Date.now()-started,documentNumber:parsed.fields.documentNumber,field_boxes:boxes}));
 }
}finally{await worker.terminate();}
