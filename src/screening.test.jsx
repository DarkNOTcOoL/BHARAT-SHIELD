import React,{useState} from 'react';
import {describe,it,expect,vi,beforeEach,afterEach} from 'vitest';
import {render,screen,fireEvent,waitFor,cleanup,act} from '@testing-library/react';
vi.mock('tesseract.js',()=>({createWorker:vi.fn()}));
vi.mock('./api/client',()=>({API_BASE_URL:'/api',apiFetch:vi.fn()}));
import {createWorker} from 'tesseract.js';
import {apiFetch} from './api/client';
import {Screening} from './main';

const text='Name: AARAV DEM0\nDocument number: DEMO1001\nDOB: 14/03/2001\nNationality: IND\nIssuing country: IND\nExpiry: 31/12/2035';
const result=id=>({id,type:'Permit',recommendation:'MANUAL_REVIEW',status:'COMPLETED',confidence:40,result:{findings:[],ai_analysis:{checks:{},face:{status:'NOT_RUN'}}}});
function Harness({initial=null}){const [value,setValue]=useState(initial),[epoch,setEpoch]=useState(0);return <><button onClick={()=>{setValue(null);setEpoch(e=>e+1);}}>Sidebar new screening</button><Screening key={epoch} screening={value} setScreening={setValue} setPage={()=>{}}/></>;}
let worker,submitted;
beforeEach(()=>{
 vi.resetAllMocks();submitted=[];
 vi.spyOn(window,'confirm').mockReturnValue(true);
 URL.createObjectURL=vi.fn(()=> 'blob:test');URL.revokeObjectURL=vi.fn();
 worker={recognize:vi.fn().mockResolvedValue({data:{text,confidence:95}}),terminate:vi.fn().mockResolvedValue()};
 createWorker.mockResolvedValue(worker);
 apiFetch.mockImplementation(async(url,options)=>{if(url==='/api/intake/prepare')return {ok:true,json:async()=>({image:'data:image/png;base64,TEST',metadata:{method:'TEST_PREPARATION',guidance:[]}})};submitted.push(JSON.parse(options.body.get('documents_json')));return {ok:true,json:async()=>({screenings:[result('SCR-'+submitted.length)]})};});
});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
function upload(name='sample.png'){fireEvent.change(document.querySelector('#doc-upload'),{target:{files:[new File(['test'],name,{type:'image/png'})]}});fireEvent.change(document.querySelector('.document-row select'),{target:{value:'Permit'}});}
async function extract(){fireEvent.click(screen.getByRole('button',{name:'Extract text locally'}));await screen.findByRole('heading',{name:'Review extracted fields'});}
async function submit(){fireEvent.click(screen.getByRole('button',{name:'Run local checks'}));await screen.findByRole('heading',{name:'Screening evidence'});}

describe('screening lifecycle regression',()=>{
 it('preserves original-image suggestions when QR-excluded OCR disagrees',async()=>{
  apiFetch.mockResolvedValueOnce({ok:true,json:async()=>({image:'data:image/png;base64,TEST',metadata:{method:'QR_MASK',qr_regions:[[[0,0],[10,0],[10,10],[0,10]]],guidance:[]}})});
  worker.recognize.mockResolvedValueOnce({data:{text:'Name: AARAV DEMO\nDocument number: DEM0O5201',confidence:95}}).mockResolvedValueOnce({data:{text:'Name: AARAV DEMO\nDocument number: DEMO5201',confidence:50}});
  render(<Harness/>);upload();await extract();expect(screen.getByLabelText('Document number').value).toBe('DEMO5201');expect(screen.getByText(/Original\/prepared OCR disagree/,{selector:'p'})).toBeTruthy();expect(screen.getByText('DEM0O5201',{selector:'td'})).toBeTruthy();await submit();expect(JSON.parse(submitted[0][0].ocr_notes).disagreements).toContain('documentNumber');
 });
 it('can use original-image OCR without preparation',async()=>{
  render(<Harness/>);upload();fireEvent.click(screen.getByLabelText(/Prepare OCR locally/));await extract();expect(apiFetch).not.toHaveBeenCalled();expect(worker.recognize.mock.calls[0][0]).toBeInstanceOf(File);
 });
 it('recovers when preparation fails instead of leaving Processing stuck',async()=>{
  apiFetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'Local preparation unavailable'})});render(<Harness/>);upload();fireEvent.click(screen.getByRole('button',{name:'Extract text locally'}));await screen.findByText(/Local preparation unavailable/);expect(screen.getByRole('button',{name:'Extract text locally'}).disabled).toBe(false);await extract();
 });
 it('completes ten consecutive screenings with a clean enabled form after every result',async()=>{
  render(<Harness/>);
  for(let i=0;i<10;i++){
   expect(document.querySelectorAll('.document-row').length).toBe(0);
   upload('sample-'+i+'.png');expect(screen.getByRole('button',{name:'Extract text locally'}).disabled).toBe(false);
   await extract();await submit();fireEvent.click(screen.getByRole('button',{name:'New screening',exact:true}));
   expect(screen.getByRole('button',{name:'Extract text locally'}).disabled).toBe(true);
  }
  expect(submitted).toHaveLength(10);expect(submitted.every(d=>d.length===1)).toBe(true);
 });
 it('resets history results and the sidebar entry path',async()=>{
  render(<Harness initial={result('OLD')}/>);fireEvent.click(screen.getByRole('button',{name:'Sidebar new screening'}));upload();await extract();await submit();fireEvent.click(screen.getByRole('button',{name:'Sidebar new screening'}));upload('second.png');expect(screen.getByRole('button',{name:'Extract text locally'}).disabled).toBe(false);
 });
 it('preserves digit zero and sends separate raw versus reviewed snapshots',async()=>{
  render(<Harness/>);upload();await extract();expect(screen.getByLabelText('Name').value).toBe('AARAV DEM0');fireEvent.change(screen.getByLabelText('Name'),{target:{value:'AARAV DEMO'}});await submit();expect(submitted[0][0].ocr_fields.name).toBe('AARAV DEM0');expect(submitted[0][0].name).toBe('AARAV DEMO');expect(submitted[0][0].ocr_text).toContain('AARAV DEM0');
 });
 it('recovers after OCR failure and verification failure without refreshing',async()=>{
  worker.recognize.mockRejectedValueOnce(Error('OCR test failure'));render(<Harness/>);upload();fireEvent.click(screen.getByRole('button',{name:'Extract text locally'}));await screen.findByText(/OCR test failure/);expect(screen.getByRole('button',{name:'Extract text locally'}).disabled).toBe(false);await extract();apiFetch.mockResolvedValueOnce({ok:false,status:503,json:async()=>({detail:'Backend unavailable'})});fireEvent.click(screen.getByRole('button',{name:'Run local checks'}));await screen.findByText(/Backend unavailable/);expect(screen.getByRole('button',{name:'Run local checks'}).disabled).toBe(false);await submit();
 });
 it('cancels OCR and ignores its late result',async()=>{
  let finish;worker.recognize.mockImplementationOnce(()=>new Promise(r=>finish=r));render(<Harness/>);upload();fireEvent.click(screen.getByRole('button',{name:'Extract text locally'}));await waitFor(()=>expect(worker.recognize).toHaveBeenCalled());fireEvent.click(screen.getByRole('button',{name:'Cancel & clear'}));await act(async()=>finish({data:{text,confidence:90}}));expect(document.querySelectorAll('.document-row').length).toBe(0);expect(screen.queryByRole('heading',{name:'Review extracted fields'})).toBeNull();upload('new.png');await extract();expect(worker.terminate).toHaveBeenCalled();
 });
 it('ignores verification responses from a cancelled request',async()=>{
  let finish;render(<Harness/>);upload();await extract();apiFetch.mockImplementationOnce(()=>new Promise(r=>finish=r));fireEvent.click(screen.getByRole('button',{name:'Run local checks'}));await waitFor(()=>expect(finish).toBeTypeOf('function'));fireEvent.click(screen.getByRole('button',{name:'Cancel & clear'}));await act(async()=>finish({ok:true,json:async()=>({screenings:[result('STALE')]})}));expect(screen.queryByRole('heading',{name:'Screening evidence'})).toBeNull();upload('new.png');expect(screen.getByRole('button',{name:'Extract text locally'}).disabled).toBe(false);
 });
 it('terminates a worker which finishes initialization after reset',async()=>{
  let finish;createWorker.mockImplementationOnce(()=>new Promise(r=>finish=r));render(<Harness/>);upload();fireEvent.click(screen.getByRole('button',{name:'Extract text locally'}));fireEvent.click(screen.getByRole('button',{name:'Cancel & clear'}));await act(async()=>finish(worker));expect(worker.recognize).not.toHaveBeenCalled();expect(worker.terminate).toHaveBeenCalled();expect(screen.queryByRole('heading',{name:'Review extracted fields'})).toBeNull();
 });
 it('honors discard confirmation and clears OCR edits on reset',async()=>{
  render(<Harness/>);upload();await extract();window.confirm.mockReturnValueOnce(false);fireEvent.click(screen.getByRole('button',{name:'Clear & Start Again'}));expect(screen.getByLabelText('Name').value).toBe('AARAV DEM0');fireEvent.click(screen.getByRole('button',{name:'Clear & Start Again'}));expect(screen.queryByLabelText('Name')).toBeNull();expect(document.querySelectorAll('.document-row').length).toBe(0);
 });
 it('locks document selection during extraction',async()=>{
  let finish;worker.recognize.mockImplementationOnce(()=>new Promise(r=>finish=r));render(<Harness/>);upload();fireEvent.click(screen.getByRole('button',{name:'Extract text locally'}));await waitFor(()=>expect(worker.recognize).toHaveBeenCalled());expect(document.querySelector('.capture-controls').disabled).toBe(true);fireEvent.click(screen.getByRole('button',{name:'Cancel & clear'}));await act(async()=>finish({data:{text,confidence:90}}));
 });
});
