import {it,expect} from 'vitest';
import {parseStructuredOCR,layoutText} from './ocrParser';
const parse=(text,type='Permit')=>parseStructuredOCR({text},type);
it('preserves ambiguous multi-token numbers when geometry is unavailable',()=>{
 for(const number of ['DEMO5201','ZX938475','AB1234Z9','987601']){
 const r=parse(`Document number: ${number} PLFAK\nName: PERSON EXAMPLE\nDOB: 2001-03-14`);
 expect(r.fields.documentNumber).toBe(number+' PLFAK');expect(r.notes.source_values.documentNumber).toBe(number+' PLFAK');expect(r.notes.warnings.length).toBeGreaterThan(0);
 }
});
it('never silently truncates a contiguous identifier to match a demo or guessed pattern',()=>{
 expect(parse('Document number: DEMO5201PLFAK').fields.documentNumber).toBe('DEMO5201PLFAK');
 expect(parse('Document number: AA12345XYZ').fields.documentNumber).toBe('AA12345XYZ');
});
it('reads values on the next line without consuming another label',()=>{
 const r=parse('Document number:\nAB773811\nName: FIRST LAST\nDOB:\nNationality: IND');
 expect(r.fields.documentNumber).toBe('AB773811');expect(r.fields.dob).toBe('');expect(r.fields.name).toBe('FIRST LAST');
});
it('does not combine subsequent fields with document number',()=>{
 expect(parse('Document number: AB001 DOB: 2000-01-01\nName: PERSON').fields.documentNumber).toBe('AB001');
});
it('keeps visa and passport reference separate',()=>{
 const r=parse('Passport number: P1234567\nVisa number: V8765432','Visa');expect(r.fields.documentNumber).toBe('V8765432');expect(r.fields.passportReference).toBe('P1234567');
});
it('uses unique format candidates, not preset values',()=>{
 expect(parse('ABCDE1234F','PAN Card').fields.documentNumber).toBe('ABCDE1234F');
 expect(parse('ABCDE1234F\nQWERT8765J','PAN Card').fields.documentNumber).toBe('');
 expect(parse('1234 5678 9012','Aadhaar Card').fields.documentNumber).toBe('123456789012');
});
it('keeps O/0 and real alphanumeric endings unchanged',()=>{
 expect(parse('Name: DEM0 PERSON\nDocument number: O0193B').fields).toMatchObject({name:'DEM0 PERSON',documentNumber:'O0193B'});
});
it('uses word bounding boxes to separate distant noise',()=>{
 const words=[['Document',0,100],['number:',110,210],['AB88712',230,360],['PLFAK',900,1000]].map(([text,x0,x1])=>({text,bbox:{x0,x1,y0:0,y1:20}}));
 const data={text:'Document number: AB88712 PLFAK',blocks:[{paragraphs:[{lines:[{words}]}]}]};
 expect(layoutText(data)).toContain('|');expect(parseStructuredOCR(data,'Permit').fields.documentNumber).toBe('AB88712');
});
it('does not invent information from arbitrary unlabelled noise',()=>{
 expect(parse('random OCR text 71883 something').fields.documentNumber).toBe('');
});
