import React from 'react';
import {describe,it,expect,vi,beforeEach,afterEach} from 'vitest';
import {render,screen,fireEvent,waitFor,cleanup,act} from '@testing-library/react';
vi.mock('../api/client',()=>({apiFetch:vi.fn()}));
import {apiFetch} from '../api/client';
import {EvidenceSection,DecisionCenter} from './EvidencePanels';
import {DemoContent} from './DemoReadiness';
import RegistryGraph,{IdentityDetails} from './RegistryGraph';
import {useLocalResource} from './LocalResource';
const ok=d=>({ok:true,json:async()=>d});
beforeEach(()=>vi.resetAllMocks());afterEach(cleanup);
describe('integrated console',()=>{
 it('does not mount costly inspection images until expanded and unmounts them on close',()=>{
  render(<EvidenceSection title="Inspection"><img src="/api/image" alt="Detailed inspection"/></EvidenceSection>);
  expect(screen.queryByAltText('Detailed inspection')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Inspection'}));expect(screen.getByAltText('Detailed inspection')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Inspection'}));expect(screen.queryByAltText('Detailed inspection')).toBeNull();
 });
 it('uses shared saved evidence without fetching for each lane and keeps unknown risk unassessed',()=>{
  const refresh=vi.fn();render(<DecisionCenter screening={{id:'S1',status:'COMPLETED',confidence:50,recommendation:'MANUAL_REVIEW',result:{ai_analysis:{risk_score:{score:null},checkpoint_decision_center:{decision_readiness:'INCOMPLETE',lanes:[{key:'registry',title:'Registry',status:'INCOMPLETE',headline:'No reference'}],top_reasons:[{code:'MISSING',message:'Review missing reference'}]}}}}} onRefresh={refresh}/>);
  expect(screen.getByText('UNASSESSED')).toBeTruthy();expect(apiFetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'All evidence lanes'}));expect(screen.getByText('No reference')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Refresh saved evidence'}));expect(refresh).toHaveBeenCalledOnce();
 });
 it('shows readiness errors and retries without exposing supervisor seed to officers',async()=>{
  apiFetch.mockImplementation(async path=>path.includes('scenarios')?ok({scenarios:[]}):{ok:false,status:503,json:async()=>({detail:'Model files unavailable'})});
  render(<DemoContent role="officer"/>);await screen.findByText('Model files unavailable');expect(screen.queryByRole('button',{name:'Prepare all synthetic demo data'})).toBeNull();
  apiFetch.mockResolvedValue(ok({overall:'READY',checks:[]}));fireEvent.click(screen.getByRole('button',{name:'Run preflight again'}));await screen.findByText('READY');
 });
 it('reports seed failure and re-enables the supervisor action',async()=>{
  apiFetch.mockImplementation(async(path,opts)=>opts?.method==='POST'?{ok:false,status:409,json:async()=>({detail:'Reference conflict'})}:ok({overall:'READY',checks:[],scenarios:[]}));
  render(<DemoContent role="supervisor"/>);fireEvent.click(screen.getByRole('button',{name:'Prepare all synthetic demo data'}));await screen.findByText('Reference conflict');expect(screen.getByRole('button',{name:'Prepare all synthetic demo data'}).disabled).toBe(false);
 });
 it('does not allow stale identity loads to replace the currently selected identity',async()=>{
  let finish;apiFetch.mockImplementation(path=>path==='/a'?new Promise(r=>finish=r):Promise.resolve(ok({name:'Current'})));
  function View({path}){const {data}=useLocalResource(path);return <p>{data?.name||'Loading'}</p>;}
  const view=render(<View path="/a"/>);view.rerender(<View path="/b"/>);await screen.findByText('Current');await act(async()=>finish(ok({name:'Stale'})));expect(screen.queryByText('Stale')).toBeNull();
 });
 it('loads linked identities through the native registry and hides seed controls for officers',async()=>{
  apiFetch.mockImplementation(async path=>ok(path.includes('summary')?{counts:{identities:1}}:{identities:[{id:'ID1',canonical_name:'FICTIONAL PERSON',dob:'2000-01-01',nationality:'IND',identity_status:'ACTIVE'}]}));
  render(<RegistryGraph role="officer"/>);await screen.findByText('FICTIONAL PERSON');expect(screen.queryByRole('button',{name:'Prepare individual reference sets'})).toBeNull();expect(screen.getByRole('button',{name:'Open identity graph'})).toBeTruthy();
 });
 it('submits supervisor linkage with an audit reason and reloads the saved identity',async()=>{
  apiFetch.mockResolvedValue(ok({identity:{id:'ID1',canonical_name:'FICTIONAL PERSON'},documents:[],alerts:[],travel_events:[],document_relations:[],biometric_references:[]}));
  render(<IdentityDetails id="ID1" supervisor onBack={()=>{}}/>);await screen.findByText('FICTIONAL PERSON · ID1');
  fireEvent.click(screen.getByRole('button',{name:'Supervisor registry actions'}));fireEvent.click(screen.getByRole('button',{name:'Link a document'}));
  fireEvent.change(screen.getByLabelText('Existing document record ID'),{target:{value:'REG-ONE'}});fireEvent.change(screen.getByLabelText('Reason (at least 10 characters)'),{target:{value:'Checked fictional document link'}});
  fireEvent.submit(screen.getByRole('button',{name:'Link document'}).closest('form'));
  await screen.findByText('Change saved with audit history.');
  const call=apiFetch.mock.calls.find(([p,o])=>o?.method==='POST');expect(call[0]).toBe('/api/registry2/identities/ID1/link-document');expect(JSON.parse(call[1].body)).toEqual({record_id:'REG-ONE',relationship:'LINKED',reason:'Checked fictional document link'});
 });
});
