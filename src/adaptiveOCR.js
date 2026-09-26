export function needsLayoutRetry(data,parsed){return (Number(data.confidence)||0)<65||['name','documentNumber','dob'].some(k=>!parsed.fields[k]);}
export function chooseLayoutRead(primary,retry){
 const keys=Object.keys(primary.fields),conflicts=keys.filter(k=>primary.fields[k]&&retry.fields[k]&&primary.fields[k]!==retry.fields[k]);
 const added=keys.filter(k=>!primary.fields[k]&&retry.fields[k]),lost=keys.filter(k=>primary.fields[k]&&!retry.fields[k]);
 return {useRetry:!conflicts.length&&!lost.length&&added.length>0,conflicts,added};
}

// v6.3: conservative whole-read ranking for same-geometry preprocessing fallbacks.
// This does not invent/correct characters; it only chooses between actual local Tesseract reads.
export function ocrReadScore(data,parsed){
 const confidence=Math.max(0,Math.min(100,Number(data?.confidence)||0));
 const text=String(data?.text||'');
 const usefulChars=(text.match(/[A-Za-z0-9]/g)||[]).length;
 const fields=parsed?.fields||{};
 const extracted=['name','documentNumber','dob','expiry','nationality'].filter(k=>String(fields[k]||'').trim()).length;
 return Math.round((confidence + Math.min(18,usefulChars/28) + extracted*4)*100)/100;
}
export function needsVariantFallback(data){
 const confidence=Number(data?.confidence)||0;
 const useful=(String(data?.text||'').match(/[A-Za-z0-9]/g)||[]).length;
 return confidence<78 || useful<90;
}
export function rankOCRReads(reads,parse){
 return (reads||[]).map(r=>{const parsed=parse(r.data);return {...r,parsed,score:ocrReadScore(r.data,parsed)}})
   .sort((a,b)=>b.score-a.score || (Number(b.data?.confidence)||0)-(Number(a.data?.confidence)||0));
}
