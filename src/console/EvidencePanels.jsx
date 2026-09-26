import {useId,useState} from 'react';
import DecisionBoundary from './DecisionBoundary';
export const label=value=>String(value??'Not recorded').replaceAll('_',' ');
export function Metrics({items}){return <dl className="console-metrics">{items.map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v??'Not recorded'}</dd></div>)}</dl>;}
export function EvidenceSection({title,children,initialOpen=false}){
 const [open,setOpen]=useState(initialOpen);const id=useId();
 return <section className="panel console-section"><h2><button type="button" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(v=>!v)}>{title}<span aria-hidden="true">{open?'−':'+'}</span></button></h2>{open&&<div id={id} className="console-section-body"><DecisionBoundary>{children}</DecisionBoundary></div>}</section>;
}
export function DecisionCenter({screening,busy,error,onRefresh}){
 const c=screening.result?.ai_analysis?.checkpoint_decision_center;
 const risk=screening.result?.ai_analysis?.risk_score;
 return <section className="panel console-center"><div className="console-heading"><div><div className="eyebrow">CHECKPOINT DECISION CENTER</div><h2>{label(c?.checkpoint_recommendation||screening.recommendation)}</h2><p>Review the evidence before recording an officer decision.</p></div><button className="secondary-btn" disabled={busy} onClick={onRefresh}>{busy?'Refreshing…':'Refresh saved evidence'}</button></div>
 {error&&<p role="alert" className="registry-error">{error}</p>}
 <Metrics items={[["Rule risk",risk?.score==null?'UNASSESSED':`${risk.score}/100 · ${risk.band}`],["Check coverage",`${screening.confidence??0}%`],["Readiness",label(c?.decision_readiness||'REFRESH_REQUIRED')],["Case status",screening.status]]}/>
 <p>Risk points are prototype rules, not a fraud probability. Coverage measures completed checks.</p>
 {(c?.top_reasons||[]).length>0&&<div className="console-priority"><h3>Priority evidence</h3><ul>{c.top_reasons.slice(0,4).map((r,i)=><li key={i}><strong>{label(r.code)}</strong>: {r.message}</li>)}</ul></div>}
 {c?<EvidenceSection title="All evidence lanes"><div className="console-lanes">{(c.lanes||[]).map(l=><article key={l.key} className={'console-lane '+l.status}><h3>{l.title}</h3><strong>{label(l.status)}</strong><p>{l.headline}</p><ul>{(l.evidence||[]).map((e,i)=><li key={i}>{e}</li>)}</ul>{l.officer_action&&<p>Officer action: {l.officer_action}</p>}</article>)}</div><p>CLEAR means no configured review threshold was crossed. It does not prove authenticity.</p></EvidenceSection>:<p>The summary is unavailable or needs refresh. Detailed saved evidence remains below.</p>}
 </section>;
}
export function CaptureEvidence({analysis}){
 const c=analysis.capture_intelligence||{},o=analysis.ocr_strategy||{};
 return <><h3>Capture and OCR</h3><Metrics items={[["Glare",label(c.glare?.status)],["Lighting",label(c.illumination?.status)],["Skew",c.skew?.skew_angle_degrees==null?'Not recorded':`${c.skew.skew_angle_degrees}°`],["Boundary",label(c.boundary?.status)],["Fallback reads",o.multi_ocr?.performed?o.multi_ocr.read_count:'Not performed'],["Selected read",o.multi_ocr?.selected||o.preprocessing?.primary||'Primary']]}/>{(c.guidance||[]).map((g,i)=><p key={i}>{g}</p>)}<p>Preprocessing supports readability. The retained original remains the evidence source.</p><h3>Recorded processing times</h3><Metrics items={Object.entries(analysis.timing||{}).filter(([k,v])=>k.endsWith('_ms')&&typeof v==='number').map(([k,v])=>[label(k),`${v} ms`])}/><p>{analysis.timing?.scope}</p></>;
}
export function LayoutEvidence({analysis}){
 const l=analysis.forensic_assist?.template_layout,v=analysis.forensic_assist?.issuer_visual_security;
 return <>{l&&<><h3>Layout and security zones</h3><Metrics items={[["Status",label(l.status)],["Layout index",l.layout_anomaly_index],["Field boxes",l.field_box_count],["Profile",l.document_type]]}/><p>{l.reason}</p><ul>{(l.signals||[]).map((s,i)=><li key={i}>{label(s.code)}: {s.field||'Document'} — {s.message}</li>)}</ul></>}{v&&<><h3>Synthetic issuer visual references</h3><Metrics items={[["Status",label(v.status)],["Anomaly index",v.visual_anomaly_index],["Template",v.template_reference?.template_version],["Issuer",v.template_reference?.issuer_name]]}/><ul>{(v.feature_results||[]).map((f,i)=><li key={i}>{f.label||f.feature_code}: {label(f.status)}{f.score!=null?` · score ${f.score}`:''}</li>)}</ul><p>{v.reason}</p></>}<p>Broad layout checks and bundled fictional references do not authenticate official templates, holograms or UV/IR features.</p></>;
}
export function RegistryGraphEvidence({value:r}){
 if(!r)return <p>No linked identity graph recorded for this screening.</p>;
 return <><h3>Synthetic linked registry</h3><p><strong>{label(r.status)}</strong> · {r.message}</p>{r.identity&&<p>{r.identity.canonical_name} · {r.identity.id} · {r.identity.nationality}</p>}<Metrics items={[["Linked documents",r.linked_documents?.length??0],["Travel events",r.travel_events?.length??0],["Alerts",r.alerts?.length??0],["Issuer templates",r.issuer_templates?.length??0]]}/>{(r.alerts||[]).map((a,i)=><p key={i}><strong>{label(a.alert_type)} · {a.severity}</strong>: {a.reason}</p>)}<p>{r.limitation||'Fictional local demonstration data only.'}</p></>;
}
export function TravelEvidence({analysis}){
 const t=analysis.travel_intelligence,v=analysis.visa_intelligence;
 return <>{v&&<><h3>Visa checks</h3><p>{label(v.status)}</p><p>{v.reason}</p><Metrics items={Object.entries(v.observed_fields||{}).map(([k,x])=>[label(k),x||'Not extracted'])}/><ul>{(v.findings||[]).map((f,i)=><li key={i}>{f.message}</li>)}</ul></>}{t?<><h3>Travel consistency</h3><Metrics items={[["Status",label(t.status)],["Travel events",t.travel_event_count],["Entries",t.entry_count],["Exits",t.exit_count]]}/>{(t.visa_assessments||[]).map((v,i)=><p key={i}><strong>{v.document_number} · {label(v.status)}</strong><br/>Entries observed: {v.entries_observed_in_registry} / {v.allowed_entries??'Not encoded'} · {v.visa_type}<br/>{v.valid_from||'?'} to {v.expiry||'?'} · Stay: {v.duration_of_stay||'Not encoded'}</p>)}<ul>{(t.findings||[]).map((f,i)=><li key={i}>{label(f.code)}: {f.message}</li>)}</ul>{(t.stamp_comparisons||[]).map((x,i)=><p key={i}>OCR stamp cue: {x.observed?.event_type} {x.observed?.country_code} {x.observed?.event_date||'Date unreadable'} · {label(x.status)}</p>)}<ul>{(t.gaps||[]).map((g,i)=><li key={i}>{g}</li>)}</ul></>:<p>No travel consistency assessment recorded.</p>}<p>Local synthetic travel data only. These checks do not decide admissibility.</p></>;
}
