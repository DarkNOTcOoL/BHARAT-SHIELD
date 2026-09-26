// No registry, QR payload, demo values or identity presets are used here.
const labels={name:'(?:full\\s+name|name)',dob:'(?:date\\s+of\\s+birth|dob)',nationality:'(?:nationality|country\\s+code)',issuerCountry:'(?:issuing\\s+country|issuer\\s+country)',issueDate:'(?:issue\\s+date|date\\s+of\\s+issue)',expiry:'(?:date\\s+of\\s+expiry|expiry(?:\\s+date)?|expiration(?:\\s+date)?)',gender:'(?:gender|sex)',issuingAuthority:'issuing\\s+authority',passportReference:'passport\\s*(?:no\\.?|number)',documentNumber:'(?:document|permit|id|passport|visa|licen[cs]e|dl|pan|epic|aadhaar|adhaar|uid)\\s*(?:no\\.?|number|#)',visaType:'(?:visa\\s*(?:type|class|category)|type\\s+of\\s+visa)',numberOfEntries:'(?:number\\s+of\\s+entries|no\\.?\\s+of\\s+entries|entries)',validFrom:'(?:valid\\s+from|validity\\s+from)',durationOfStay:'(?:duration\\s+of\\s+(?:each\\s+)?stay|max(?:imum)?\\s+stay)'};
const date=/\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}\s+[A-Z]{3,9}\s+\d{4})\b/i;
const extraLabels={dob:'(?:birth\\s+date|d\\.?o\\.?b\\.?)',expiry:'(?:valid\\s+(?:until|upto|up\\s+to)|expires(?:\\s+on)?)',issueDate:'(?:issued\\s+on)',documentNumber:'(?:document\\s+id|identity\\s+number)'};
const allLabels=new RegExp('\\b(?:'+[...Object.values(labels),...Object.values(extraLabels)].join('|')+')\\s*[:#]','i');
export function layoutText(data){
 const lines=[];
 for(const block of data.blocks||[])for(const paragraph of block.paragraphs||[])for(const line of paragraph.lines||[]){
   const words=line.words||[];if(!words.length){if(line.text)lines.push(line.text.trim());continue;}
   let value='',last=null;
   for(const word of words){const box=word.bbox;if(!word.text)continue;
     const gap=last&&box?box.x0-last.x1:0,height=box?box.y1-box.y0:15;
     value+=(value?(gap>Math.max(36,height*2.5)&&/[:#]\s*\S/.test(value)?' | ':' '):'')+word.text;last=box;
   }lines.push(value);
 }
 return lines.length?lines.join('\n'):data.text||'';
}
export function parseStructuredOCR(data,type,legacy={}){
 const text=layoutText(data),lines=text.replace(/\r/g,'').split('\n').map(v=>v.trim()).filter(Boolean),warnings=[],sources={};
 const result=Object.fromEntries(Object.keys(labels).map(k=>[k,'']));
 function read(key){
   const pattern=new RegExp('^\\s*(?:'+labels[key]+(extraLabels[key]?'|'+extraLabels[key]:'')+')(?=\\s|[:#.-]|$)\\s*[:#.-]?\\s*(.*)$','i');
   for(let i=0;i<lines.length;i++)for(const segment of lines[i].split(/\s*\|\s*|\t+| {3,}/)){
     const match=segment.match(pattern);if(!match)continue;
     let value=match[1].trim();
     if(!value&&i+1<lines.length&&!allLabels.test(lines[i+1]))value=lines[i+1].split(/\s*\|\s*|\t+| {3,}/)[0].trim();
     const next=value.search(allLabels);if(next>=0)value=value.slice(0,next).trim();
     if(value){sources[key]=value;return value;}
   }return '';
 }
 for(const key of Object.keys(labels))result[key]=read(key);
 if(type==='Visa'){
   const match=text.match(/^\s*(?:visa|document|id)\s*(?:no\.?|number)\s*[:#.-]?\s*([^\n|]+)/im);
   result.documentNumber=match?.[1]?.trim()||'';
 }else result.passportReference='';
 const rawNumber=result.documentNumber;
 if(rawNumber){
   const parts=rawNumber.split(/\s+/);
   // Preserve numeric groups (e.g. UID); never truncate a contiguous alphanumeric token.
   if(parts.length>1&&parts.every(p=>/^\d+$/.test(p)))result.documentNumber=parts.join('');
   else if(parts.length>1){warnings.push('Document number contains multiple tokens without a reliable layout boundary. They were retained; verify the full value on the original.');}
   result.documentNumber=result.documentNumber.toUpperCase().replace(/^[#:]+|[,:;]+$/g,'');
 }
 // Document-specific patterns, not specific identities. Accept only a unique candidate.
 const formats={'PAN Card':/\b[A-Z]{5}\d{4}[A-Z]\b/gi,'Voter ID (EPIC)':/\b[A-Z]{3}\d{7}\b/gi,'Aadhaar Card':/\b\d{4}[ \t]?\d{4}[ \t]?\d{4}\b/g};
 const format=formats[type];
 if(format){const candidates=[...new Set((text.match(format)||[]).map(v=>v.replace(/\s/g,'').toUpperCase()))];
   if(!result.documentNumber&&candidates.length===1)result.documentNumber=candidates[0];
   else if(candidates.length>1)warnings.push('Multiple document-number candidates. Select the correct value from the image.');
   if(result.documentNumber&&!new RegExp('^(?:'+format.source.replace(/\\b/g,'')+')$','i').test(result.documentNumber))warnings.push('Document number does not fit the supported type pattern; it has NOT been shortened to force a match.');
 }
 for(const key of ['dob','issueDate','expiry','validFrom'])if(result[key])result[key]=result[key].match(date)?.[0]||result[key];
 if(type!=='Visa')for(const key of ['visaType','numberOfEntries','validFrom','durationOfStay'])result[key]='';
 // MRZ parser remains available for passports. Do not apply generic legacy label guesses.
 if(type==='Passport'&&/^P<[A-Z<]{3}/im.test(text))for(const key of ['name','dob','nationality','documentNumber','expiry'])if(!result[key])result[key]=legacy[key]||'';
 if(!result.name){const surname=text.match(/^\s*(?:surname|family name)\s*[:#]\s*([^\n|]+)/im)?.[1],given=text.match(/^\s*(?:given names?|first name)\s*[:#]\s*([^\n|]+)/im)?.[1];result.name=[surname,given].filter(Boolean).join(' ');}
 for(const key of Object.keys(result))result[key]=result[key].normalize('NFKC').trim().slice(0,180);
 if(!data.blocks?.length)warnings.push('OCR word geometry unavailable; line-based extraction used.');
 else if(text.includes(' | '))warnings.push('Distant OCR words were separated using image positions; inspect the extraction source values.');
 if(result.documentNumber&&/\d[A-Z]{3,}$/i.test(result.documentNumber)&&!['PAN Card'].includes(type))warnings.push('Letters after digits in document number: inspect the source. They may be legitimate; no automatic truncation.');
 return {fields:result,notes:{method:'LOCAL_LAYOUT_LABELS_V60_VISA',source_values:sources,warnings,layout_text:text.slice(0,20000)}};
}
