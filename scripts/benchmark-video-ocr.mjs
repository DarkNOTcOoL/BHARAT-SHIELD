// Actual OCR measurements on fictional cards. Expected values only evaluate output.
import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';
import {createWorker} from 'tesseract.js';import {parseStructuredOCR} from '../src/ocrParser.js';
import {needsLayoutRetry,chooseLayoutRead} from '../src/adaptiveOCR.js';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url))),directory=process.argv[2];
if(!directory)throw Error('Provide prepared-input directory.');
const cases=JSON.parse(fs.readFileSync(path.join(root,'demo_samples/video_demo/expected_scenarios.json'))),results=[];
const worker=await createWorker('eng',1,{workerPath:path.join(root,'node_modules/tesseract.js/src/worker-script/node/index.js'),corePath:path.join(root,'dist/ocr/core'),langPath:path.join(root,'dist/ocr/tessdata'),gzip:true,cacheMethod:'none'});
const aliases={document_number:'documentNumber',issue_date:'issueDate',issuer_country:'issuerCountry'};
try{for(const c of cases){
 let start=performance.now();const baseline=await worker.recognize(path.join(root,'demo_samples/video_demo',c.file),{}, {text:true,blocks:true});const base=parseStructuredOCR(baseline.data,'Permit'),baseline_ms=Math.round(performance.now()-start);
 start=performance.now();let {data}=await worker.recognize(path.join(directory,c.file),{}, {text:true,blocks:true});let parsed=parseStructuredOCR(data,'Permit'),retry=false,adopted=false,conflicts=[];
 if(needsLayoutRetry(data,parsed)){retry=true;await worker.setParameters({tessedit_pageseg_mode:'11'});const second=await worker.recognize(path.join(directory,c.file),{}, {text:true,blocks:true});await worker.setParameters({tessedit_pageseg_mode:'3'});const p=parseStructuredOCR(second.data,'Permit'),choice=chooseLayoutRead(parsed,p);conflicts=choice.conflicts;if(choice.useRetry){data=second.data;parsed=p;adopted=true;}}
 const keys=['name','document_number','dob','nationality','issuer_country','issue_date','expiry'],matches=p=>keys.filter(k=>p.fields[aliases[k]||k]===c.printed[k]).length;
 results.push({file:c.file,degraded:c.degraded,baseline_ms,updated_ocr_ms:Math.round(performance.now()-start),baseline_exact_fields:matches(base),updated_exact_fields:matches(parsed),total_fields:keys.length,retry,adopted,conflicts,confidence:data.confidence,fields:parsed.fields,raw_text:data.text});
}}finally{await worker.terminate();}
const clean=results.filter(r=>!r.degraded),median=key=>{const v=clean.map(x=>x[key]).sort((a,b)=>a-b);return (v[3]+v[4])/2;};
const report={scope:'Synthetic fixtures only; same engine/parser, original image vs prepared/adaptive pipeline. Sequential timing excludes worker startup, Python preparation and UI. Not a real-ID benchmark.',clean_field_total:clean.length*7,baseline_exact:clean.reduce((s,r)=>s+r.baseline_exact_fields,0),updated_exact:clean.reduce((s,r)=>s+r.updated_exact_fields,0),median_original_ms:median('baseline_ms'),median_updated_ms:median('updated_ocr_ms'),cases:results};
fs.writeFileSync(path.join(root,'OCR_BENCHMARK_V56.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,cases:results.map(r=>({file:r.file,fields:r.updated_exact_fields,confidence:r.confidence,retry:r.retry}))}));
