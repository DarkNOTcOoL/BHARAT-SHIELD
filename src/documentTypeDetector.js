const TYPES=['Passport','Visa','Aadhaar Card','Voter ID (EPIC)','Driving Licence','PAN Card','National ID','Permit','Travel Authorization'];

function normalized(text=''){
  return String(text).normalize('NFKC').replace(/\r/g,'').toUpperCase();
}
function compact(text=''){
  return normalized(text).replace(/[^A-Z0-9<]+/g,' ');
}
function add(scores,evidence,type,points,label){
  scores[type]=(scores[type]||0)+points;
  evidence[type].push({label,points});
}

export function detectDocumentType(textOrData){
  const text=typeof textOrData==='string'?textOrData:(textOrData?.text||'');
  const t=normalized(text), c=compact(text);
  const scores=Object.fromEntries(TYPES.map(x=>[x,0]));
  const evidence=Object.fromEntries(TYPES.map(x=>[x,[]]));
  const hit=(re)=>re.test(t);
  const chit=(re)=>re.test(c);

  // Passport: MRZ is intentionally the strongest cue because the word "passport"
  // can also appear on visas as a reference field.
  if(/(?:^|\n)P<[A-Z0-9<]{3}/m.test(t)) add(scores,evidence,'Passport',12,'TD3 passport MRZ');
  if(hit(/\bPASSPORT\b/)) add(scores,evidence,'Passport',5,'PASSPORT label');
  if(hit(/\bREPUBLIC\s+OF\s+INDIA\b|\bPASSPORT\s+NO\b|\bPLACE\s+OF\s+BIRTH\b/)) add(scores,evidence,'Passport',3,'passport-specific labels');
  if(hit(/\bNATIONALITY\b/)) add(scores,evidence,'Passport',1,'nationality field');

  // Visa: require visa-specific terms rather than the passport reference alone.
  if(hit(/\bE[- ]?VISA\b|\bVISA\b/)) add(scores,evidence,'Visa',7,'VISA label');
  if(hit(/\b(?:NO\.?\s+OF\s+)?ENTRIES\b/)) add(scores,evidence,'Visa',4,'entries field');
  if(hit(/\bDURATION\s+OF\s+(?:EACH\s+)?STAY\b|\bMAX(?:IMUM)?\s+STAY\b/)) add(scores,evidence,'Visa',4,'duration-of-stay field');
  if(hit(/\bVALID\s+FROM\b|\bVISA\s+(?:TYPE|CLASS|CATEGORY)\b/)) add(scores,evidence,'Visa',3,'visa validity/type field');
  if(hit(/\bPASSPORT\s*(?:NO\.?|NUMBER)\b/) && hit(/\bVISA\b/)) add(scores,evidence,'Visa',2,'passport reference on visa');

  // Aadhaar / UIDAI.
  if(hit(/\bAADHAAR\b|\bAADHAR\b|\bUIDAI\b|UNIQUE\s+IDENTIFICATION\s+AUTHORITY\s+OF\s+INDIA/)) add(scores,evidence,'Aadhaar Card',10,'UIDAI/Aadhaar identifier');
  if(/\b\d{4}\s*\d{4}\s*\d{4}\b/.test(t)) add(scores,evidence,'Aadhaar Card',5,'12-digit Aadhaar-like number');
  if(hit(/\bGOVERNMENT\s+OF\s+INDIA\b|\bYEAR\s+OF\s+BIRTH\b|\bYOB\b/)) add(scores,evidence,'Aadhaar Card',1,'common Aadhaar labels');

  // PAN.
  if(hit(/PERMANENT\s+ACCOUNT\s+NUMBER/)) add(scores,evidence,'PAN Card',10,'Permanent Account Number label');
  if(hit(/INCOME\s+TAX\s+DEPARTMENT/)) add(scores,evidence,'PAN Card',5,'Income Tax Department label');
  if(/\b[A-Z]{5}\d{4}[A-Z]\b/.test(c)) add(scores,evidence,'PAN Card',7,'PAN-format identifier');
  if(hit(/\bFATHER'?S\s+NAME\b/) && hit(/\bPAN\b|PERMANENT\s+ACCOUNT/)) add(scores,evidence,'PAN Card',2,'PAN identity labels');

  // Election Commission / EPIC.
  if(hit(/ELECTION\s+COMMISSION\s+OF\s+INDIA/)) add(scores,evidence,'Voter ID (EPIC)',9,'Election Commission label');
  if(hit(/ELECTOR(?:'S)?\s+PHOTO\s+IDENTITY\s+CARD|\bEPIC\b/)) add(scores,evidence,'Voter ID (EPIC)',8,'EPIC/card label');
  if(/\b[A-Z]{3}\d{7}\b/.test(c)) add(scores,evidence,'Voter ID (EPIC)',5,'EPIC-format identifier');

  // Driving licence.
  if(hit(/\bDRIVING\s+LICEN[CS]E\b|\bDRIVER'?S\s+LICEN[CS]E\b/)) add(scores,evidence,'Driving Licence',9,'Driving Licence label');
  if(hit(/\bDL\s*(?:NO\.?|NUMBER)\b/)) add(scores,evidence,'Driving Licence',5,'DL number label');
  if(hit(/\bTRANSPORT\s+DEPARTMENT\b|\bVALID\s+TILL\b|\bCOV\b/)) add(scores,evidence,'Driving Licence',2,'licence-specific labels');
  if(/\b[A-Z]{2}\s*[- ]?\s*\d{2}\s*[- ]?\s*\d{4,13}\b/.test(c)) add(scores,evidence,'Driving Licence',4,'licence-format identifier');

  if(hit(/\bNATIONAL\s+(?:IDENTITY|ID)\s+(?:CARD|DOCUMENT)\b/)) add(scores,evidence,'National ID',8,'National ID label');
  if(hit(/\bIDENTITY\s+NUMBER\b/) && !hit(/\bAADHAAR\b|\bPAN\b|\bEPIC\b/)) add(scores,evidence,'National ID',2,'generic identity-number label');
  if(hit(/\bPERMIT\b/)) add(scores,evidence,'Permit',8,'Permit label');
  if(hit(/\bPERMIT\s*(?:NO\.?|NUMBER)\b/)) add(scores,evidence,'Permit',3,'Permit number label');
  if(hit(/\bTRAVEL\s+AUTHORI[ZS]ATION\b|\bELECTRONIC\s+TRAVEL\s+AUTHORI[ZS]ATION\b|\bETA\b/)) add(scores,evidence,'Travel Authorization',9,'Travel Authorization label');

  const ranked=TYPES.map(type=>({type,score:scores[type],evidence:evidence[type]})).sort((a,b)=>b.score-a.score||a.type.localeCompare(b.type));
  const best=ranked[0], second=ranked[1];
  const margin=best.score-second.score;
  let status='UNDETERMINED';
  if(best.score>=8 && margin>=3) status='DETECTED';
  else if(best.score>=6) status='AMBIGUOUS';
  const confidence=status==='UNDETERMINED'?0:Math.max(0,Math.min(100,Math.round((best.score/(best.score+Math.max(second.score,2)))*100)));
  return {
    status,
    detectedType:status==='UNDETERMINED'?'':best.type,
    confidence,
    score:best.score,
    margin,
    runnerUp:second.type,
    runnerUpScore:second.score,
    evidence:best.evidence,
    ranked:ranked.filter(x=>x.score>0).slice(0,4),
    method:'LOCAL_EXPLAINABLE_DOCUMENT_TYPE_ROUTER_V1',
    limitation:'Rule-weighted OCR evidence for routing only; not an issuer-authenticity model. Officer may override the detected type.'
  };
}

export function recommendedPageSegMode(type){
  if(['Aadhaar Card','PAN Card','Voter ID (EPIC)','Driving Licence'].includes(type)) return '11';
  if(['Passport','Visa'].includes(type)) return '6';
  return '3';
}
