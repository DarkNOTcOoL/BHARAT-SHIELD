import {useState} from 'react';
import {safeBoxes} from './fieldGeometry';
import './inspector.css';
const aliases={documentNumber:'document_number',issuerCountry:'issuer_country',issueDate:'issue_date',issuingAuthority:'issuing_authority',passportReference:'passport_reference',visaType:'visa_type',numberOfEntries:'number_of_entries',validFrom:'valid_from',durationOfStay:'duration_of_stay'};
export default function DocumentInspector({src,boxes=[],fields={},rawFields={},analysis,regions=[]}){
 const [selected,setSelected]=useState(null),[visible,setVisible]=useState(true);
 const items=safeBoxes(boxes),suspects=safeBoxes(regions);
 const row=items.find(r=>r.field===selected),key=aliases[selected]||selected;
 const qr=analysis?.signed_qr?.comparisons?.find(r=>r.field===key);
 const registry=analysis?.registry?.fields?.find(r=>r.field===key);
 const read=(values,k)=>values?.[k]??values?.[aliases[k]||k];
 return <section className="document-inspector"><h3>Visual field inspector</h3>
 <p>Blue: OCR location. Amber: low confidence, an officer correction, or an AI/manual inspection region. Boxes are not a tamper verdict.</p>
 <label><input type="checkbox" checked={visible} onChange={e=>setVisible(e.target.checked)}/> Show boxes</label>
 <div className="inspector-canvas"><img src={src} alt="Original document with selectable OCR field locations"/>
 {visible&&items.map(r=>{const changed=read(fields,r.field)!==undefined&&read(rawFields,r.field)!==undefined&&read(fields,r.field)!==read(rawFields,r.field);const warn=changed||r.confidence==null||r.confidence<65;return <button type="button" key={r.field} className={'ocr-box '+(warn?'uncertain':'')} style={{left:r.box[0]*100+'%',top:r.box[1]*100+'%',width:r.box[2]*100+'%',height:r.box[3]*100+'%'}} aria-label={'Inspect '+r.field} aria-pressed={selected===r.field} onClick={()=>setSelected(r.field)} title={r.field+' — OCR '+(r.confidence??'unknown')}><span>{r.field}</span></button>;})}
 {visible&&suspects.map((r,i)=>{const ai=r.source==='ROBUST_PCA_PATCH_ANOMALY';return <div key={i} className="inspection-region" style={{left:r.box[0]*100+'%',top:r.box[1]*100+'%',width:r.box[2]*100+'%',height:r.box[3]*100+'%'}} title={ai?'AI anomaly region — officer review required':'Repeated-feature region: manual inspection only'}><span>{ai?`AI anomaly ${r.anomaly_score??''}`:'Repeat-pattern candidate'}</span></div>;})}
 </div>
 {!items.length&&<p>No unambiguous field geometry available for this document. Text extraction and manual review remain available; no boxes are fabricated.</p>}
 {!!items.length&&<div className="inspector-field-list">{items.map(r=><button type="button" key={r.field} onClick={()=>setSelected(r.field)}>{r.field}</button>)}</div>}
 {row&&<div className="inspector-details" aria-live="polite"><h4>{selected}</h4><dl><dt>Source OCR text</dt><dd>{row.text||'Not recorded'}</dd><dt>Word confidence (mean)</dt><dd>{row.confidence==null?'Unknown':row.confidence+'%'} — not authenticity probability</dd><dt>Parsed OCR</dt><dd>{read(rawFields,selected)||'Not extracted'}</dd><dt>Officer-reviewed value</dt><dd>{read(fields,selected)||'Not supplied'}</dd><dt>Signed demo QR</dt><dd>{qr?.signed||'Not available'} · printed/signed: {qr?.printed_vs_signed||'NOT_COMPARED'}</dd><dt>Synthetic registry</dt><dd>{registry?.registry||'Not available'} · reviewed/registry: {registry?.status||'NOT_COMPARED'}</dd><dt>Registry / signed QR</dt><dd>{qr?.registry_vs_signed||'NOT_COMPARED'}</dd></dl><p>Source positions are browser-supplied. QR signature validity is a separate check. Missing evidence is not a conflict.</p></div>}
 </section>;
}
