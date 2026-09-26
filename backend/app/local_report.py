"""Escaped, self-contained HTML report; browser Print can save a local PDF."""
import json
from html import escape

def render_report(payload,review,events):
    def e(value):return escape(str(value if value is not None else '—'),quote=True)
    def table(headers,rows):
        return '<table><thead><tr>'+''.join('<th>'+e(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+e(v)+'</td>' for v in r)+'</tr>' for r in rows)+'</tbody></table>'
    a=payload.get('result',{}).get('ai_analysis',{});r=a.get('registry',{});x=a.get('extraction',{});face=a.get('face',{});live=a.get('liveness',{})
    sections=[('<h1>BHARATSHIELD screening report</h1><p class="warning">SYNTHETIC DEMONSTRATION REGISTRY — No government connection. This report is not an authenticity certificate.</p>'),
      '<p>Local HTML report. Use your browser’s Print → Save as PDF for a PDF copy. No external resources are loaded.</p>',
      table(['Item','Value'],[(k,payload.get(k,'—')) for k in ['id','case_id','created_at','exported_at','type','person','number','recommendation','status','document_hash','hash_integrity_ok']]),
      '<h2>1. Document checks</h2><p>Tamper/photo-integrity signals are prototype inspection aids, not validated universal fraud classifiers. Stamp verification is not implemented. Missing evidence is not proof of fraud.</p>'+table(['Check','Status'],a.get('checks',{}).items()),
      '<h2>2. Registry comparison</h2><p>'+e(r.get('status','NOT RUN'))+' — '+e(r.get('message','Legacy screening: comparison unavailable.'))+'</p><p>Reference: '+e(r.get('record',{}).get('id') if r.get('record') else 'None')+' / version '+e(r.get('record',{}).get('version') if r.get('record') else 'None')+'</p>'+table(['Field','Reviewed upload','Synthetic registry','Result'],[(f['label'],f['uploaded'],f['registry'],f['status']) for f in r.get('fields',[])]),
      '<h2>3. Person comparison</h2><p>Face status: '+e(face.get('status','NOT_RUN'))+'. Cosine similarity: '+e(face.get('cosine_similarity','Not measured'))+'. Active liveness: '+e(live.get('status','NOT_RUN'))+'. Similarity is not a probability of identity; active liveness is prototype replay resistance, not certified PAD.</p>',
      '<h2>OCR review evidence</h2><p>Submitted by '+e(x.get('reviewed_by','Not recorded'))+' at '+e(x.get('reviewed_at','Not recorded'))+'. Browser-supplied OCR, not independently attested.</p>'+table(['Field','Parsed OCR','Reviewed value'],[(k,x.get('parsed_fields',{}).get(k,'Not recorded'),v) for k,v in x.get('reviewed_fields',{}).items()]),
      '<h3>Recorded corrections</h3>'+table(['Field','Before','After'],[(c['field'],c['before'],c['after']) for c in x.get('corrections',[])])+('<p>No parsed OCR snapshot supplied; correction history unavailable.</p>' if not x.get('parsed_fields_supplied') else ''),
      '<h3>Raw OCR</h3><pre>'+e(x.get('raw_text',payload.get('result',{}).get('ocr_text','Not recorded')))+'</pre>',
      '<h2>Findings, including cross-document checks</h2>'+table(['Code','Severity','Observation'],[(f['code'],f['severity'],f['message']) for f in payload.get('result',{}).get('findings',[])]),
      '<h2>Manual review</h2>'+table(['Field','Value'],(review or {'state':'Not queued'}).items()),
      '<h2>Decision and audit history</h2>'+table(['Time','Officer','Event'],[(v['time'],v['officer'],v['action']) for v in events]),
      '<p>Hashes detect byte changes against the stored reference, not document authenticity. A machine administrator can alter local databases. Protect downloaded reports as identity data.</p>']
    if x.get('intake_notes_browser_supplied'):sections.append('<h2>OCR intake notes (browser supplied)</h2><pre>'+e(x['intake_notes_browser_supplied'])+'</pre>')
    for key in ['checkpoint_decision_center','risk_score','signed_qr','duplicates','timing','forensic_assist','person_comparison_history','liveness_history','person_assurance']:
        if key in a:sections.append('<h2>'+e(key.replace('_',' '))+'</h2><pre>'+e(json.dumps(a[key],indent=2,ensure_ascii=False))+'</pre>')
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>'+e(payload['id'])+' — Local report</title><style>body{font:14px Arial,sans-serif;color:#172a40;margin:32px;line-height:1.5}h1{font-size:26px}h2{margin-top:28px}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{border:1px solid #bcc9d5;padding:8px;text-align:left;overflow-wrap:anywhere}th{background:#edf2f6}pre{white-space:pre-wrap;overflow-wrap:anywhere}.warning{padding:12px;border:2px solid #a45b00}thead{display:table-header-group}tr{break-inside:avoid}@media print{body{margin:0;font-size:10pt}@page{size:A4;margin:16mm}}</style><body>'+''.join(sections)+'</body></html>'
