import {useState} from 'react';
export default function ForensicAssist({analysis,screeningId}){
 const [view,setView]=useState('anomaly');if(!analysis)return null;
 const ai=analysis.tamper_ai||{};
 const photo=analysis.photo_substitution||{};
 const stamp=analysis.stamp_seal||{};
 const visual=analysis.issuer_visual_security||{};
 const affected=(ai.affected_fields||[]).filter(Boolean);
 const photoCues=(photo.cues||[]).filter(Boolean);
 const photoRan=!!photo.status&&!['MODEL_UNAVAILABLE','MODEL_ERROR','NO_PORTRAIT_DETECTED'].includes(photo.status);
 return <section className="panel registry-panel">
  <h2>AI-assisted document integrity analysis</h2>
  <p><strong>{ai.status||analysis.status}</strong> · Authenticity: {analysis.authenticity}</p>
  <p>Local unsupervised forensic ML compares patches inside this document using compression, noise, edge and texture features. These indices are <strong>not</strong> probabilities of fraud and do not replace officer review.</p>
  <div className="evidence-summary">
   <div><span>Tamper anomaly index</span><strong>{ai.max_anomaly_score ?? 'N/A'}</strong><small>{ai.strong_region_count ?? 0} strong region(s)</small></div>
   <div><span>Photo substitution</span><strong>{photo.status||'NOT RUN'}</strong><small>Index: {photo.photo_integrity_index ?? 'N/A'}</small></div>
   <div><span>Patches analyzed</span><strong>{ai.patch_count ?? 'N/A'}</strong><small>Total forensic time: {analysis.processing_ms ?? 'N/A'} ms</small></div>
   <div><span>Visa stamp/seal</span><strong>{stamp.status||'NOT APPLICABLE'}</strong><small>{stamp.candidate_count??0} candidate region(s)</small></div>
  </div>
  {affected.length>0&&<p><strong>OCR field region(s) intersecting strong anomaly:</strong> {affected.join(', ')}</p>}
  <div className="photo-integrity-card">
   <h3>Portrait / replaced-photo inspection</h3>
   <p><strong>{photo.status||'NOT RUN'}</strong>{photo.face_count!=null?` · Face-like regions: ${photo.face_count}`:''}</p>
   <p>{photo.reason||'Portrait analysis was not recorded for this screening.'}</p>
   {photoCues.length>0&&<p><strong>Review cues:</strong> {photoCues.join(', ')}</p>}
   {photo.frame_detected!=null&&<p>Portrait frame localization: <strong>{photo.frame_detected?'detected':'estimated around AI-detected face'}</strong>.</p>}
   <p className="muted">YuNet localizes the portrait face. Boundary, JPEG-residual, noise-pattern and overlapping-tamper cues are then inspected locally. This is not a calibrated replacement-photo probability.</p>
  </div>
  {stamp.status&&stamp.status!=='NOT_APPLICABLE'&&<div className="photo-integrity-card"><h3>Visa stamp / seal inspection</h3><p><strong>{stamp.status}</strong> · Candidates: {stamp.candidate_count??0}</p><p>{stamp.reason}</p><p className="muted">Country-agnostic local CV/forensic assistance only. It does not authenticate an issuer stamp or prove a stamp was added/removed.</p></div>}
  {visual.status&&<div className="photo-integrity-card"><h3>Synthetic issuer visual references</h3><p><strong>{visual.status}</strong> · Template: {visual.template_reference?.template_version||'No local reference'}</p><p>{visual.reason}</p><p className="muted">Hash-bound bundled synthetic reference features only. This does not authenticate a real government/issuer document or verify holograms, UV/IR features or paper substrate.</p></div>}
  {ai.reason&&<p>{ai.reason}</p>}
  <div className="batch-switch">
   <button className="secondary-btn" onClick={()=>setView('anomaly')}>AI anomaly map</button>
   <button className="secondary-btn" onClick={()=>setView('photo-integrity')} disabled={!photoRan}>Photo integrity</button>
   <button className="secondary-btn" onClick={()=>setView('stamp-integrity')} disabled={!stamp.status||stamp.status==='NOT_APPLICABLE'}>Visa stamp/seal</button>
   <button className="secondary-btn" onClick={()=>setView('visual-security')} disabled={!visual.template_reference}>Issuer visual references</button>
   <button className="secondary-btn" onClick={()=>setView('layout')}>Layout / security zones</button>
   <button className="secondary-btn" onClick={()=>setView('texture')}>Texture heatmap</button>
   <button className="secondary-btn" onClick={()=>setView('repeats')}>Repeated-feature candidates</button>
   <button className="secondary-btn" onClick={()=>setView('residual')}>JPEG residual</button>
  </div>
  <img className="evidence-image" src={`/api/screening/${screeningId}/image?view=${view}`} alt={'Local forensic inspection view: '+view}/>
  <p>{analysis.copy_move_candidates?.length||0} repeated-feature pair(s).</p>
  {(analysis.limitations||[]).map((v,i)=><p key={i}>{v}</p>)}
 </section>;
}
