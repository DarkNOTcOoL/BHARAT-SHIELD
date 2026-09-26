import React from 'react';
import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import SignedEvidence from './SignedEvidence';
import AccountControls from './AccountControls';
vi.mock('./api/client',()=>({apiFetch:vi.fn()}));
import {apiFetch} from './api/client';
afterEach(()=>{cleanup();vi.resetAllMocks();});
it('does not invent signed evidence for legacy screenings',()=>{const {container}=render(<SignedEvidence/>);expect(container.textContent).toBe('');});
it('displays valid signature separately from field conflict',()=>{
 render(<SignedEvidence analysis={{signed_qr:{signature_status:'SIGNATURE_VALID',message:'Signature valid',comparison_status:'SIGNED_DATA_CONFLICT',required_by_registry:true,claims:{credential_id:'DEMO-TEST'},comparisons:[{field:'dob',reviewed:'2002-03-14',signed:'2001-03-14',registry:'2001-03-14',printed_vs_signed:'CONFLICT',registry_vs_signed:'MATCH'}]}}}/>);
 expect(screen.getByText('SIGNATURE_VALID')).toBeTruthy();expect(screen.getByText(/SIGNED_DATA_CONFLICT/)).toBeTruthy();expect(screen.getByText('2002-03-14')).toBeTruthy();expect(screen.getByText(/does not authenticate/)).toBeTruthy();
});
it('does not expose administration controls to officers',()=>{render(<AccountControls role="officer"/>);expect(screen.queryByText('Load accounts and sessions')).toBeNull();expect(screen.getByText('Change password and sign out')).toBeTruthy();});
it('loads supervisor account list and reports API failure',async()=>{
 apiFetch.mockResolvedValueOnce({ok:true,json:async()=>({users:[{username:'demo',role:'officer',enabled:true}],sessions:[],session_policy:'Local session policy'})});
 render(<AccountControls role="supervisor"/>);fireEvent.click(screen.getByText('Load accounts and sessions'));await screen.findByText(/demo · officer/);
 apiFetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'Integrity unavailable'})});fireEvent.click(screen.getByText('Check audit integrity'));await screen.findByText('Integrity unavailable');
});
it('requires explicit confirmation before disabling an account',async()=>{
 apiFetch.mockResolvedValue({ok:true,json:async()=>({users:[{username:'demo',role:'officer',enabled:true}],sessions:[]})});vi.spyOn(window,'confirm').mockReturnValue(false);
 render(<AccountControls role="supervisor"/>);fireEvent.click(screen.getByText('Load accounts and sessions'));await screen.findByText('Disable');fireEvent.click(screen.getByText('Disable'));expect(apiFetch).toHaveBeenCalledTimes(1);vi.restoreAllMocks();
});
