import React from 'react';
import {it,expect,afterEach} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import {needsLayoutRetry,chooseLayoutRead} from './adaptiveOCR';
import {parseStructuredOCR} from './ocrParser';
import RiskEvidence from './RiskEvidence';
afterEach(cleanup);
it('only adopts a retry that adds values without conflicts or lost fields',()=>{
 const first={fields:{name:'CASEY',dob:'',documentNumber:'AX729381'}};
 expect(needsLayoutRetry({confidence:90},first)).toBe(true);
 expect(chooseLayoutRead(first,{fields:{name:'CASEY',dob:'1998-07-21',documentNumber:'AX729381'}}).useRetry).toBe(true);
 expect(chooseLayoutRead(first,{fields:{name:'CASEY',dob:'1998-07-21',documentNumber:'AX729382'}}).useRetry).toBe(false);
});
it('skips retry on clear complete OCR',()=>{expect(needsLayoutRetry({confidence:90},{fields:{name:'CASEY',dob:'1998-07-21',documentNumber:'AX729381'}})).toBe(false);});
it('supports common English date labels',()=>{
 const r=parseStructuredOCR({text:'Name: SAMPLE PERSON\nDocument ID: ZX728394\nBirth date: 1998-07-21\nIssued on: 2022-01-15\nValid until: 2035-12-31'},'Permit');
 expect(r.fields).toMatchObject({documentNumber:'ZX728394',dob:'1998-07-21',issueDate:'2022-01-15',expiry:'2035-12-31'});
});
it('shows missing evidence as unassessed, not zero',()=>{
 render(<RiskEvidence value={{score:null,band:'UNASSESSED',evidence_status:'INCOMPLETE',policy_version:'test',factors:[],gaps:['Reference not found'],method:'Rules',limitation:'Not a probability'}}/>);
 expect(screen.getByText('UNASSESSED')).toBeTruthy();expect(screen.queryByRole('meter')).toBeNull();expect(screen.getByText('Reference not found')).toBeTruthy();
});
