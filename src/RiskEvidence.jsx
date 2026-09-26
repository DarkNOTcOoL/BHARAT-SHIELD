export default function RiskEvidence({value}){
 if(!value)return <section className="panel registry-panel"><h2>Screening risk</h2><p>No saved risk score for this older screening. Start a new screening to calculate it.</p></section>;
 return <section className="panel registry-panel"><h2>Synthetic-reference risk score</h2><h3 style={{color:value.band==='LOW'?'#14733d':['HIGH','CRITICAL'].includes(value.band)?'#b42318':'#945800'}}>{value.score==null?'UNASSESSED':`${value.score} / 100 · ${value.band}`}</h3>
 <p>{value.evidence_status.replaceAll('_',' ')} · {value.policy_version}</p><p>{value.limitation}</p>
 {value.score!=null&&<meter min="0" max="100" low="1" high="30" optimum="0" value={value.score} aria-label="Prototype rule risk points" style={{width:'100%',height:24}}/>}
 {value.factors.length?<table><thead><tr><th>Rule family</th><th>Points</th><th>Reason</th></tr></thead><tbody>{value.factors.map(f=><tr key={f.group}><th>{f.group.replaceAll('_',' ')}</th><td>+{f.points}</td><td>{f.reason}</td></tr>)}</tbody></table>:<p>No weighted inconsistency detected. Missing evidence can still require review.</p>}
 {!!value.gaps.length&&<><h4>Unresolved evidence</h4><ul>{value.gaps.map((g,i)=><li key={i}>{g}</li>)}</ul></>}<p>{value.method} Officer acceptance is recorded separately.</p></section>;
}
