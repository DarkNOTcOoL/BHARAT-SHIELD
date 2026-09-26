import {useEffect,useRef,useState} from 'react';
import {apiFetch} from './api/client';

const labels={FRONT:'Face forward',TURN_LEFT:'Turn your head left',TURN_RIGHT:'Turn your head right'};

export default function LivenessCameraCapture({screeningId,onResult,onCancel}){
 const video=useRef(null),stream=useRef(null),alive=useRef(true),submitting=useRef(false);
 const [challenge,setChallenge]=useState(null),[index,setIndex]=useState(0),[frames,setFrames]=useState({}),[ready,setReady]=useState(false),[busy,setBusy]=useState(true),[error,setError]=useState('');
 const stop=()=>{stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;};
 useEffect(()=>{alive.current=true;let cancelled=false;
  (async()=>{
   try{
    const r=await apiFetch(`/api/screening/${screeningId}/face/liveness/challenge`,{method:'POST'});const data=await r.json();
    if(!r.ok)throw Error(data.detail||'Could not start liveness challenge.');if(cancelled)return;setChallenge(data);
    if(!navigator.mediaDevices?.getUserMedia)throw Error('Camera unavailable in this browser.');
    const s=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:1280},height:{ideal:720}}});
    if(cancelled){s.getTracks().forEach(t=>t.stop());return;}stream.current=s;if(video.current)video.current.srcObject=s;setBusy(false);
   }catch(e){if(!cancelled){setError(e.message||'Could not start liveness challenge.');setBusy(false);}}
  })();
  return()=>{cancelled=true;alive.current=false;stop();};
 },[screeningId]);
 const capture=()=>{
  if(!challenge||!ready||!video.current?.videoWidth||submitting.current)return;
  const step=challenge.steps[index],v=video.current,canvas=document.createElement('canvas'),scale=Math.min(1,1280/Math.max(v.videoWidth,v.videoHeight));
  canvas.width=Math.round(v.videoWidth*scale);canvas.height=Math.round(v.videoHeight*scale);const ctx=canvas.getContext('2d');if(!ctx){setError('Capture unavailable.');return;}
  ctx.drawImage(v,0,0,canvas.width,canvas.height);
  canvas.toBlob(blob=>{if(!blob||!alive.current){setError('Capture failed. Please retry.');return;}const file=new File([blob],`${step.toLowerCase()}.jpg`,{type:'image/jpeg'});const next={...frames,[step]:file};setFrames(next);
   if(index<challenge.steps.length-1){setIndex(index+1);return;}submit(next);
  },'image/jpeg',.94);
 };
 const submit=async all=>{
  if(submitting.current)return;submitting.current=true;setBusy(true);setError('');stop();
  try{
   const form=new FormData();form.append('challenge_id',challenge.challenge_id);form.append('front',all.FRONT);form.append('turn_left',all.TURN_LEFT);form.append('turn_right',all.TURN_RIGHT);
   const r=await apiFetch(`/api/screening/${screeningId}/face/liveness`,{method:'POST',body:form});const data=await r.json();if(!r.ok)throw Error(data.detail||'Liveness verification failed.');onResult(data);
  }catch(e){setError(e.message||'Liveness verification failed.');submitting.current=false;setBusy(false);}
 };
 const step=challenge?.steps?.[index];
 return <div className="camera-box liveness-box">
  <h3>Active liveness challenge</h3>
  <p>This randomized three-frame head-turn check adds replay resistance. It is not certified presentation-attack detection.</p>
  {challenge&&<div className="liveness-step"><strong>Step {index+1} of {challenge.steps.length}: {labels[step]}</strong><span>{challenge.instructions?.[step]}</span></div>}
  <video ref={video} autoPlay playsInline muted aria-label="Active liveness camera" onLoadedData={()=>setReady(true)}/>
  {error&&<p role="alert">{error}</p>}{busy&&!error&&<p role="status">{submitting.current?'Checking head-turn motion locally…':'Starting local challenge…'}</p>}
  <div className="camera-actions"><button type="button" className="primary-btn" disabled={!ready||busy||!step} onClick={capture}>Capture this step</button><button type="button" className="secondary-btn" disabled={busy} onClick={()=>{setFrames({});setIndex(0);}}>Restart captures</button><button type="button" className="secondary-btn" onClick={()=>{stop();onCancel();}}>Cancel liveness</button></div>
  {challenge&&<p className="muted">Challenge expires after {challenge.expires_in_seconds} seconds. Frames are analyzed locally and are not retained by the backend; hashes and result metadata are retained as evidence.</p>}
 </div>;
}
