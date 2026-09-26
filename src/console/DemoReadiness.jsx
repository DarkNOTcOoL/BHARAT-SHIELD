import {useRef,useState} from 'react';
import {EvidenceSection,Metrics} from './EvidencePanels';
import {requestJSON,useLocalResource} from './LocalResource';

export function DemoContent({role}){
 const [revision,setRevision]=useState(0),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');const working=useRef(false);
 const readiness=useLocalResource('/api/demo/readiness',revision),scenarios=useLocalResource('/api/demo/scenarios');
 async function seed(){if(working.current)return;working.current=true;setBusy(true);setError('');setNotice('');try{const d=await requestJSON('/api/demo/seed-all',{method:'POST'});setNotice(d.message||'Synthetic demo data prepared. Existing records preserved.');setRevision(x=>x+1);}catch(e){setError(e.message);}finally{working.current=false;setBusy(false);}}
 return <><p>Check local dependencies and prepare fictional references before the demonstration. Existing records are preserved.</p>
 {readiness.loading?<p role="status">Running local preflight…</p>:readiness.error?<p role="alert">{readiness.error}</p>:<><h3>{readiness.data?.overall}</h3><Metrics items={[["Blocking items",readiness.data?.blocking_count],["Warnings",readiness.data?.warning_count],["Scenarios",readiness.data?.scenario_count]]}/><ul>{(readiness.data?.checks||[]).map((c,i)=><li key={i}><strong>{c.status} · {c.name}</strong>: {c.detail}</li>)}</ul></>}
 <div className="console-tools"><button className="secondary-btn" disabled={readiness.loading||busy} onClick={()=>setRevision(x=>x+1)}>Run preflight again</button>{role==='supervisor'&&<button className="primary-btn" disabled={busy} onClick={seed}>{busy?'Preparing…':'Prepare all synthetic demo data'}</button>}</div>
 {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
 <h3>Judge demo scenarios</h3>{scenarios.loading?<p role="status">Loading scenario guide…</p>:scenarios.error?<p role="alert">{scenarios.error}</p>:<div className="console-scenarios">{(scenarios.data?.scenarios||[]).map(s=><article key={s.key} className="console-scenario"><h3>{s.title}</h3><strong>{s.document_type} · {s.expected}</strong><p>{s.why}</p><p>{s.talking_point}</p><p><code>{s.sample}</code></p><a className="secondary-btn" target="_blank" rel="noopener noreferrer" href={'/api/demo/sample/'+encodeURIComponent(s.key)}>Open sample</a></article>)}</div>}
 <p>Expected outcomes are scenario guidance. Current input, reference edits and existing evidence determine the actual result.</p></>;
}
export default function DemoReadiness({role}){return <EvidenceSection title="SIH26188 Demo Readiness"><DemoContent role={role}/></EvidenceSection>;}
