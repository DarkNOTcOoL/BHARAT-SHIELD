export default function SignedEvidence({analysis={}}){
 const qr=analysis.signed_qr,d=analysis.duplicates,t=analysis.timing;
 if(!qr)return null;
 return <section className="panel registry-panel"><h2>Signed demo QR — local verification</h2>
 <p>Synthetic issuer only. A valid signature does not authenticate the printed document or its holder.</p>
 <h3>{qr.signature_status}</h3><p>{qr.message}</p><p>Field comparison: {qr.comparison_status} · Signed QR required by reference: {qr.required_by_registry?'Yes':'No'}</p>
 {qr.claims&&<><p>Credential: {qr.claims.credential_id} · Reference: {qr.reference_status}</p><small>Trusted public-key SHA-256: {qr.key_fingerprint}</small>
 <div className="registry-scroll"><table><thead><tr><th>Field</th><th>Reviewed OCR</th><th>Signed QR</th><th>Registry</th><th>Printed / signed</th><th>Registry / signed</th></tr></thead><tbody>{qr.comparisons.map(r=><tr key={r.field}><th>{r.field}</th><td>{r.reviewed||'—'}</td><td>{r.signed||'—'}</td><td>{r.registry||'—'}</td><td>{r.printed_vs_signed}</td><td>{r.registry_vs_signed}</td></tr>)}</tbody></table></div></>}
 {d&&<><h3>Local history candidates</h3><p>{d.status} · {d.searched_count} screenings searched</p><p>{d.limitation}</p>{d.candidates.map(c=><p key={c.screening_id}>{c.screening_id}: {c.reasons.join(', ')} {c.requires_review?'— REVIEW REQUIRED':''}</p>)}</>}
 {t&&<p>Local document processing: {t.local_document_processing_ms} ms. {t.scope}</p>}
 </section>;
}
