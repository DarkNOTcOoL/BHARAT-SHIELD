import React from 'react';
import {it,expect,vi,beforeEach,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
vi.mock('./api/client',()=>({apiFetch:vi.fn(),API_BASE_URL:'/api'}));
import {apiFetch} from './api/client';
import {DecisionPanel} from './main';
const profile={role:'supervisor',officerId:'supervisor'};
let row;
beforeEach(()=>{vi.resetAllMocks();row={screening_id:'SCR-REVIEW',state:'PENDING',version:1,assigned_to:''};apiFetch.mockImplementation(async(path,options)=>{
 if(path.includes('/decision')&&options?.method==='POST')return {ok:true,json:async()=>({status:'Verified',decision:'ACCEPT',direct_supervisor_override:true})};
 if(options?.method==='POST'){const body=JSON.parse(options.body);row={...row,version:row.version+1,state:body.action==='CLAIM'?'UNDER_REVIEW':'RESOLVED',resolution:body.action==='RESOLVE'?'ACCEPT':'',assigned_to:'supervisor'};return {ok:true,json:async()=>row};}
 return {ok:true,json:async()=>({review:row})};
});});
afterEach(cleanup);

it('supervisor can directly accept a non-critical evidence-gap review without claiming it first',async()=>{
 const saved=vi.fn();render(<DecisionPanel screeningId="SCR-REVIEW" queued recommendation="MANUAL_REVIEW" directSupervisorAccept profile={profile} setScreening={saved}/>);
 fireEvent.change(screen.getByLabelText('Reason for decision'),{target:{value:'Original evidence checked and acceptable.'}});
 fireEvent.click(screen.getByRole('button',{name:'ACCEPT',exact:true}));
 await screen.findByText(/Decision: ACCEPTED/);
 expect(apiFetch.mock.calls.filter(([p,o])=>p.includes('/decision')&&o?.method==='POST')).toHaveLength(1);
 expect(screen.queryByRole('button',{name:'Claim case for review'})).toBeNull();
 expect(saved).toHaveBeenCalled();
});

it('officers still open protected review for queued cases',()=>{
 const open=vi.fn();render(<DecisionPanel screeningId="SCR-REVIEW" queued recommendation="MANUAL_REVIEW" directSupervisorAccept profile={{role:'officer'}} setScreening={()=>{}} onOpenReview={open}/>);
 fireEvent.click(screen.getByRole('button',{name:'OPEN SUPERVISOR REVIEW'}));expect(open).toHaveBeenCalled();expect(apiFetch).not.toHaveBeenCalled();
});

it('explicit recapture/review cases still use the protected supervisor workflow',async()=>{
 row.state='UNDER_REVIEW';render(<DecisionPanel screeningId="SCR-REVIEW" queued recommendation="RECAPTURE" profile={profile} setScreening={()=>{}}/>);
 fireEvent.click(screen.getByRole('button',{name:'REVIEW TO ACCEPT'}));
 await screen.findByRole('button',{name:'Confirm supervisor acceptance'});
 fireEvent.change(screen.getByLabelText('Reason for decision'),{target:{value:'Checked original and comparison.'}});
 apiFetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'Review changed. Reload before submitting.'})});
 fireEvent.click(screen.getByRole('button',{name:'Confirm supervisor acceptance'}));
 await screen.findByRole('alert');
 expect(screen.getByLabelText('Reason for decision').value).toBe('Checked original and comparison.');
 expect(screen.getByRole('button',{name:'Reload review state'})).toBeTruthy();
 expect(screen.queryByText(/Decision: ACCEPTED/)).toBeNull();
});

it('ordinary clean acceptance sends a reason and records only after server success',async()=>{
 apiFetch.mockResolvedValue({ok:true,json:async()=>({status:'Verified'})});render(<DecisionPanel screeningId="SCR-CLEAR" recommendation="REVIEW_COMPLETE_CHECKS" setScreening={()=>{}}/>);
 fireEvent.click(screen.getByRole('button',{name:'ACCEPT',exact:true}));expect(apiFetch).not.toHaveBeenCalled();expect(screen.getByRole('alert')).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Reason for decision'),{target:{value:'Checked original document.'}});fireEvent.click(screen.getByRole('button',{name:'ACCEPT',exact:true}));await screen.findByText(/Decision: ACCEPTED/);expect(apiFetch.mock.calls[0][1].body.get('reason')).toBe('Checked original document.');
});

it('blocked and revoked records keep acceptance disabled',()=>{
 render(<DecisionPanel screeningId="SCR-BLOCKED" queued recommendation="ESCALATE" escalationOnly profile={profile} setScreening={()=>{}}/>);expect(screen.getByRole('button',{name:'REVIEW TO ACCEPT'}).disabled).toBe(true);expect(screen.getByRole('button',{name:'ESCALATE',exact:true}).disabled).toBe(false);
});
