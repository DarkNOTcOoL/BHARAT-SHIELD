import React from 'react';
import {it,expect,vi,beforeEach,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
vi.mock('./api/client',()=>({apiFetch:vi.fn()}));
import {apiFetch} from './api/client';
import ReviewQueue from './ReviewQueue';
let row;
beforeEach(()=>{vi.resetAllMocks();row={screening_id:'SCR-TEST',state:'PENDING',version:1,assigned_to:'',person:'DEMO PERSON',recommendation:'MANUAL_REVIEW',reason:'Missing reference evidence'};apiFetch.mockImplementation(async(path,options)=>{
 if(options?.method==='POST'){const body=JSON.parse(options.body);row={...row,version:row.version+1,state:body.action==='CLAIM'?'UNDER_REVIEW':'RESOLVED',assigned_to:'tester'};return {ok:true,json:async()=>row};}
 return {ok:true,json:async()=>path.endsWith('/officers')?[{username:'tester',name:'Test Officer'}]:{items:[row],total:1}};
});});
afterEach(cleanup);
it('lets officers claim a case without exposing supervisor actions',async()=>{
 render(<ReviewQueue profile={{role:'officer',officerId:'tester'}} onOpen={()=>{}}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Manage review'}));
 expect(screen.queryByRole('button',{name:'Resolve review'})).toBeNull();expect(screen.queryByRole('button',{name:'Assign',exact:true})).toBeNull();
 fireEvent.change(screen.getByLabelText('Reason for review action'),{target:{value:'Inspecting original evidence.'}});fireEvent.click(screen.getByRole('button',{name:'Claim for review'}));
 await screen.findByText('Review updated and audit event recorded.');
 const call=apiFetch.mock.calls.find(([,o])=>o?.method==='POST');expect(JSON.parse(call[1].body)).toMatchObject({action:'CLAIM',expected_version:1});
});
it('sends supervisor resolution with the displayed version and reason',async()=>{
 row.state='UNDER_REVIEW';row.assigned_to='tester';row.version=2;
 render(<ReviewQueue profile={{role:'supervisor',officerId:'supervisor'}} onOpen={()=>{}}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Manage review'}));fireEvent.change(screen.getByLabelText('Reason for review action'),{target:{value:'Original reviewed; flag retained.'}});fireEvent.change(screen.getByLabelText('Resolution'),{target:{value:'FLAG'}});fireEvent.click(screen.getByRole('button',{name:'Resolve review'}));
 await screen.findByText('Review updated and audit event recorded.');const call=apiFetch.mock.calls.find(([,o])=>o?.method==='POST');expect(JSON.parse(call[1].body)).toMatchObject({action:'RESOLVE',expected_version:2,outcome:'FLAG',reason:'Original reviewed; flag retained.'});
});
it('keeps the reason when a stale review is rejected',async()=>{
 render(<ReviewQueue profile={{role:'officer',officerId:'tester'}} onOpen={()=>{}}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Manage review'}));apiFetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'Review changed. Reload before submitting.'})});fireEvent.change(screen.getByLabelText('Reason for review action'),{target:{value:'Inspecting original evidence.'}});fireEvent.click(screen.getByRole('button',{name:'Claim for review'}));
 await screen.findByRole('alert');expect(screen.getByLabelText('Reason for review action').value).toBe('Inspecting original evidence.');
});
