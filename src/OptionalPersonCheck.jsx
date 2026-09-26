import {useEffect,useRef,useState} from 'react';
import {apiFetch} from './api/client';
import LiveCameraCapture from './LiveCameraCapture';
import LivenessCameraCapture from './LivenessCameraCapture';
import './person-check.css';

export default function OptionalPersonCheck({screening,onResult,onLivenessResult}){
 const saved=screening.result?.ai_analysis?.face||{status:'NOT_RUN'};
 const liveness=screening.result?.ai_analysis?.liveness||{status:'NOT_RUN'};
 const identityHistory=screening.result?.ai_analysis?.identity_history||liveness.identity_history||{status:'NOT_RUN',candidates:[]};
 const [enabled,setEnabled]=useState(false),[camera,setCamera]=useState(false),[livenessCamera,setLivenessCamera]=useState(false),[photo,setPhoto]=useState(null),[source,setSource]=useState(''),[preview,setPreview]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const request=useRef(null),generation=useRef(0),working=useRef(false);
 const cancel=()=>{generation.current++;request.current?.abort();request.current=null;working.current=false;setBusy(false);setCamera(false);setLivenessCamera(false);setPhoto(null);};
 useEffect(()=>()=>{generation.current++;request.current?.abort();},[]);
 useEffect(()=>{if(!photo){setPreview('');return;}const url=URL.createObjectURL(photo);setPreview(url);return()=>URL.revokeObjectURL(url);},[photo]);
 const choose=(file,kind)=>{setCamera(false);setError('');setNotice('');if(!file||!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>10*1024*1024){setError('Use a JPG, PNG or WEBP up to 10 MiB.');return;}setPhoto(file);setSource(kind);};
 async function send(skip=false){
  if(working.current||(!skip&&!photo))return;working.current=true;setBusy(true);setError('');setNotice('');
  const token=++generation.current,controller=new AbortController();request.current=controller;
  const timeout=setTimeout(()=>{if(generation.current!==token)return;generation.current++;controller.abort();working.current=false;setBusy(false);setError('Comparison timed out. Reopen this screening to check whether the server saved the attempt before retrying.');},60000);
  try{
   const form=new FormData();if(!skip){form.append('photo',photo);form.append('capture_source',source);}
   const response=await apiFetch(`/api/screening/${screening.id}/face${skip?'/skip':''}`,{method:'POST',...(!skip?{body:form}:{}),signal:controller.signal});
   const data=await response.json();if(generation.current!==token)return;
   if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Comparison request failed.');
   onResult(data);setPhoto(null);setEnabled(false);setNotice(skip?'Optional person check skipped. Document screening can continue.':'Comparison saved. Review the result below. Captured image discarded from this panel.');
  }catch(e){if(generation.current===token)setError(e.message||'Local comparison failed.');}
  finally{clearTimeout(timeout);if(generation.current===token){working.current=false;setBusy(false);request.current=null;}}
 }
 const attempted=!['NOT_RUN','SKIPPED'].includes(saved.status);
 const locked=['Verified','Recapture requested'].includes(screening.status)||screening.review?.state==='RESOLVED';
 return <section className="panel face-panel optional-person"><h2>Optional person comparison</h2>
 <p>Compare the photograph on this document with one camera capture. Processing stays on this computer. Skipping does not lower document-check coverage or prevent a document decision.</p>
 <p><strong>{saved.status}</strong>{saved.reason?' — '+saved.reason:''}</p>
 {saved.cosine_similarity!==undefined&&<p>Cosine similarity: <strong>{saved.cosine_similarity}</strong>. This is not a percentage or a verified identity result.</p>}
 <p>Liveness: <strong>{liveness.status}</strong>{liveness.reason?' — '+liveness.reason:''}</p>
 {liveness.motion_checks&&<p>Head-turn evidence: opposite turns {liveness.motion_checks.opposite_turns?'observed':'not clear'}; separation {liveness.motion_checks.yaw_separation??'—'}.</p>}
 <p className="muted">The active challenge adds resistance to a static printed-photo attack, but it is not certified PAD and may not detect sophisticated video replay, masks or virtual cameras.</p>
 <div className="identity-history-box"><p><strong>Multiple-identity history:</strong> {identityHistory.status||'NOT_RUN'}</p>{identityHistory.requires_review&&<p className="review-warning">Similar liveness-passed face template(s) were found under different identity/document attributes. This is an officer-review candidate, not an identity verdict.</p>}{(identityHistory.candidates||[]).slice(0,5).map(c=><div className="identity-candidate" key={c.screening_id}><strong>{c.screening_id}</strong> · similarity {c.cosine_similarity} · {c.person_name} · {c.document_number}<br/><small>{(c.identity_differences||[]).join(', ')||'Same recorded identity fields'} — {c.candidate_type}</small></div>)}{identityHistory.method&&<p className="muted">Encrypted local SFace-template retrieval after passed liveness. Thresholds are prototype retrieval thresholds and require calibration.</p>}</div>
 {saved.capture_source&&<p>Capture source (browser-reported): {saved.capture_source}. Recorded by {saved.performed_by} at {saved.performed_at}.</p>}
 {saved.face_counts&&<p>Detected faces — document: {saved.face_counts.document??'not checked'}; person capture: {saved.face_counts.person??'not checked'}.</p>}
 {saved.face_regions&&<p>Face locations and model hashes are included in the evidence export.</p>}
 {attempted&&saved.status==='REVIEW_REQUIRED'&&<div className="liveness-actions">
  <button type="button" className="primary-btn" disabled={busy||livenessCamera||locked} onClick={()=>{setLivenessCamera(true);setCamera(false);setPhoto(null);setError('');setNotice('');}}>Run active liveness challenge</button>
  {liveness.status==='PASSED_ACTIVE_CHALLENGE'&&<strong className="liveness-pass">Active challenge passed</strong>}
  {liveness.status==='RETRY_REQUIRED'&&<strong className="review-warning">Liveness retry required</strong>}
 </div>}
 {livenessCamera&&<LivenessCameraCapture screeningId={screening.id} onCancel={()=>setLivenessCamera(false)} onResult={value=>{setLivenessCamera(false);onLivenessResult?.(value);setNotice(value.status==='PASSED_ACTIVE_CHALLENGE'?'Active liveness challenge saved.':'Liveness challenge saved; review or retry the result.');}}/>}

 {locked?<p>This case has a final decision. Reopen its supervisor review or start a new screening before adding another comparison.</p>:<>
 <label><input type="checkbox" checked={enabled} disabled={busy} onChange={e=>{cancel();setEnabled(e.target.checked);setError('');setNotice('');}}/> Enable optional person comparison</label>
 {!enabled&&!attempted&&<button type="button" className="secondary-btn" disabled={busy||saved.status==='SKIPPED'} onClick={()=>send(true)}>Skip person check</button>}
 {enabled&&<><p>Use with the person's knowledge. The face-comparison capture is discarded after processing. After a passed active-liveness challenge, BHARATSHIELD retains an encrypted local SFace biometric template for future multiple-identity candidate retrieval; raw camera frames are not stored.</p>
 <div className="batch-switch"><button type="button" className="secondary-btn" disabled={busy} onClick={()=>{setPhoto(null);setCamera(true);setError('');}}>Open live camera</button>
 <label className="secondary-btn">Upload consented test photo<input aria-label="Upload consented test photo" type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={e=>{if(e.target.files[0])choose(e.target.files[0],'UPLOADED_PHOTO');e.target.value='';}}/></label></div>
 {camera&&<LiveCameraCapture onCapture={f=>choose(f,'LIVE_CAMERA')} onCancel={()=>setCamera(false)}/>}
 {photo&&<><div className="person-preview"><figure><img src={`/api/screening/${screening.id}/image?view=original`} alt="Document photograph reference"/><figcaption>Document reference</figcaption></figure><figure><img src={preview} alt="Person capture awaiting comparison"/><figcaption>{source==='LIVE_CAMERA'?'Camera capture':'Uploaded test photo'}</figcaption></figure></div>
 <button type="button" className="primary-btn" disabled={busy} onClick={()=>send(false)}>Compare locally</button><button type="button" className="secondary-btn" disabled={busy} onClick={()=>{setPhoto(null);if(source==='LIVE_CAMERA')setCamera(true);}}>Retake / choose another</button></>}
 {!attempted&&!busy&&<button type="button" className="secondary-btn" onClick={()=>{cancel();setEnabled(false);send(true);}}>Skip person check</button>}
 </>}
 </>}
 {busy&&<p role="status">Running local person check…</p>}{busy&&<button type="button" className="secondary-btn" onClick={()=>{cancel();setEnabled(false);setNotice('Request cancelled locally. The server may already have saved it; reopen the screening to check.');}}>Cancel comparison</button>}
 {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 </section>;
}
