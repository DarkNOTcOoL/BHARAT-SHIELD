import {useEffect,useRef,useState} from 'react';

export default function LiveCameraCapture({onCapture,onCancel}){
 const video=useRef(null),stream=useRef(null),active=useRef(false),busy=useRef(false),session=useRef(0);
 const [attempt,setAttempt]=useState(0),[ready,setReady]=useState(false),[error,setError]=useState('');
 const stop=()=>{stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;};
 useEffect(()=>{
  let current=true;active.current=true;session.current++;busy.current=false;setError('');setReady(false);
  if(!navigator.mediaDevices?.getUserMedia){setError('Camera unavailable. Open this app at http://127.0.0.1:8000 in a browser with camera support. You can skip this optional check.');return()=>{active.current=false;};}
  navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:1280},height:{ideal:720}}}).then(s=>{
   if(!current){s.getTracks().forEach(t=>t.stop());return;}
   stream.current=s;if(video.current)video.current.srcObject=s;
   s.getVideoTracks().forEach(t=>t.addEventListener('ended',()=>{if(current){setReady(false);setError('Camera disconnected. Reconnect it and retry, or skip this optional check.');}}));
  }).catch(e=>{if(current)setError(e.name==='NotAllowedError'?'Camera permission denied. Allow camera access in the browser, then retry; or skip this optional check.':e.name==='NotFoundError'?'No camera found. Connect a webcam and retry, or skip this optional check.':'Camera could not start. Close other camera apps and retry, or skip this optional check.');});
  return()=>{current=false;active.current=false;session.current++;stop();};
 },[attempt]);
 const capture=()=>{
  if(busy.current||!ready||!video.current?.videoWidth)return;
  busy.current=true;
  const token=session.current;
  try{
   const v=video.current,canvas=document.createElement('canvas'),scale=Math.min(1,1600/Math.max(v.videoWidth,v.videoHeight));
   canvas.width=Math.round(v.videoWidth*scale);canvas.height=Math.round(v.videoHeight*scale);
   const ctx=canvas.getContext('2d');if(!ctx)throw Error('Capture unavailable.');
   ctx.drawImage(v,0,0,canvas.width,canvas.height);
   canvas.toBlob(blob=>{if(!active.current||session.current!==token)return;busy.current=false;if(!blob){setError('Capture failed. Please retry.');return;}stop();setReady(false);onCapture(new File([blob],'live-person.jpg',{type:'image/jpeg'}));},'image/jpeg',.94);
  }catch{busy.current=false;setError('Capture failed. Please retry.');}
 };
 return <div className="camera-box"><p>Keep one person in view, face forward and use even lighting. A camera frame alone does not verify liveness.</p>
 <video ref={video} autoPlay playsInline muted aria-label="Live person camera" onLoadedData={()=>setReady(true)}/>
 {error&&<p role="alert">{error}</p>}
 <div className="camera-actions"><button type="button" className="primary-btn" disabled={!ready} onClick={capture}>Capture person</button><button type="button" className="secondary-btn" onClick={()=>{stop();setAttempt(a=>a+1);}}>Retry camera</button><button type="button" className="secondary-btn" onClick={()=>{stop();onCancel();}}>Close camera</button></div>
 </div>;
}
