// Geometry is browser-supplied OCR evidence, not an authenticity measurement.
const clean=s=>String(s||'').normalize('NFKC').replace(/\s+/g,' ').trim().toUpperCase();
export function fieldGeometry(data,sources,dimensions){
 const [width,height]=dimensions||[];
 if(!(width>0&&height>0))return [];
 const lines=(data.blocks||[]).flatMap(b=>(b.paragraphs||[]).flatMap(p=>p.lines||[]));
 const output=[];
 for(const [field,source] of Object.entries(sources||{})){
   const target=clean(source);if(!target)continue;
   const matches=[];
   for(const line of lines){const words=(line.words||[]).filter(w=>w.text&&w.bbox);
     for(let start=0;start<words.length;start++)for(let end=start;end<Math.min(words.length,start+24);end++){
       const chosen=words.slice(start,end+1),text=clean(chosen.map(w=>w.text).join(' '));
       if(text!==target)continue;
       const x0=Math.min(...chosen.map(w=>w.bbox.x0)),y0=Math.min(...chosen.map(w=>w.bbox.y0));
       const x1=Math.max(...chosen.map(w=>w.bbox.x1)),y1=Math.max(...chosen.map(w=>w.bbox.y1));
       if(![x0,y0,x1,y1].every(Number.isFinite)||x0<0||y0<0||x1>width||y1>height||x1<=x0||y1<=y0)continue;
       const scores=chosen.map(w=>w.confidence).filter(c=>typeof c==='number'&&Number.isFinite(c)&&c>=0&&c<=100);
       matches.push({field,text:source,box:[x0/width,y0/height,(x1-x0)/width,(y1-y0)/height],confidence:scores.length===chosen.length?Math.round(scores.reduce((a,b)=>a+b,0)/scores.length):null});
     }
   }
   // Ambiguous/repeated strings are deliberately not assigned guessed locations.
   if(matches.length===1)output.push(matches[0]);
 }
 return output;
}
export function safeBoxes(boxes){
 return (Array.isArray(boxes)?boxes:[]).slice(0,40).filter(r=>r&&typeof r.field==='string'&&Array.isArray(r.box)&&r.box.length===4&&r.box.every(n=>typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=1)&&r.box[2]>0&&r.box[3]>0&&r.box[0]+r.box[2]<=1.00001&&r.box[1]+r.box[3]<=1.00001).map(r=>({...r,field:r.field.slice(0,80),text:typeof r.text==='string'?r.text.slice(0,180):'',confidence:typeof r.confidence==='number'&&Number.isFinite(r.confidence)&&r.confidence>=0&&r.confidence<=100?r.confidence:null}));
}
export function savedNotes(extraction){try{const n=JSON.parse(extraction?.intake_notes_browser_supplied||'{}');return n&&typeof n==='object'?n:{};}catch{return {};}}
// Keep valid JSON under the backend's 20,000-character limit; never slice JSON.
export function serializeNotes(notes){
 const compact={...notes,layout_text:(notes?.layout_text||'').slice(0,1500)};
 if(compact.alternative)compact.alternative={confidence:compact.alternative.confidence,fields:compact.alternative.fields};
 let value=JSON.stringify(compact);if(value.length<=20000)return value;
 return JSON.stringify({method:notes.method,field_boxes:safeBoxes(notes.field_boxes),geometry_frame:notes.geometry_frame,warnings:['Extended OCR notes omitted to fit evidence limit.'],disagreements:notes.disagreements||[]});
}
