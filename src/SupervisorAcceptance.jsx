import {useEffect,useRef,useState} from 'react';
import {apiFetch} from './api/client';

export default function SupervisorAcceptance({screeningId,profile,reason,onAccepted,onOpenReview}){
 const [review,setReview]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[revision,setRevision]=useState(0),[loaded,setLoaded]=useState(false);
 const mounted=useRef(true),saving=useRef(false);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 useEffect(()=>{let active=true;setLoaded(false);setError('');apiFetch('/api/reviews/'+screeningId).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.detail||'Could not load review.');if(active){setReview(d.review);setLoaded(true);}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[screeningId,revision]);
 async function change(action){
  if(saving.current)return;
  if(reason.trim().length<10){setError('Enter a decision reason of at least 10 characters above.');return;}
  saving.current=true;setBusy(true);setError('');
  try{
   const response=await apiFetch('/api/reviews/'+screeningId,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,expected_version:review.version,reason:reason.trim(),...(action==='RESOLVE'?{outcome:'ACCEPT'}:{})})});
   const data=await response.json();if(!mounted.current)return;if(!response.ok)throw Error(data.detail||'Review action failed.');
   setReview(data);if(action==='RESOLVE')onAccepted(data);
  }catch(e){if(mounted.current)setError(e.message);}finally{saving.current=false;if(mounted.current)setBusy(false);}
 }
 return <section className="supervisor-acceptance"><h3>Supervisor acceptance</h3><p>Review the evidence and enter your reason above. Claim the case if pending, then confirm acceptance. The server checks the displayed review version.</p>
 {!loaded&&!error&&<p>Loading review…</p>}{review&&<p>State: {review.state} · Assigned to: {review.assigned_to||'Unassigned'} · Version: {review.version}</p>}
 {review?.state==='PENDING'&&<button type="button" className="secondary-btn" disabled={busy||!!review.assigned_to&&review.assigned_to!==profile.officerId} onClick={()=>change('CLAIM')}>Claim case for review</button>}
 {review?.state==='UNDER_REVIEW'&&<button type="button" className="primary-btn" disabled={busy} onClick={()=>change('RESOLVE')}>Confirm supervisor acceptance</button>}
 {review?.state==='RESOLVED'&&<p>This review is already resolved as {review.resolution}. Reopen it through Manual Review before changing it.</p>}
 {loaded&&!review&&<p>No queued review found. Reopen the screening to refresh its decision controls.</p>}
 {review?.state==='PENDING'&&review.assigned_to&&review.assigned_to!==profile.officerId&&<p>This case is assigned to another officer. Use Manual Review to reassign it.</p>}
 <button type="button" className="secondary-btn" disabled={busy} onClick={()=>setRevision(n=>n+1)}>Reload review state</button><button type="button" className="secondary-btn" disabled={busy} onClick={onOpenReview}>Open Manual Review</button>
 {error&&<p role="alert">{error}</p>}</section>;
}
