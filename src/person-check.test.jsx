import React from 'react';
import {it,expect,vi,beforeEach,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup,waitFor,act} from '@testing-library/react';
vi.mock('./api/client',()=>({apiFetch:vi.fn(),API_BASE_URL:'/api'}));
import {apiFetch} from './api/client';
import OptionalPersonCheck from './OptionalPersonCheck';
import LiveCameraCapture from './LiveCameraCapture';
const screening={id:'SCR-PERSON',status:'Pending',result:{ai_analysis:{face:{status:'NOT_RUN'}}}};
let getUserMedia,stop,track,stream;
beforeEach(()=>{
 vi.resetAllMocks();stop=vi.fn();track={stop,addEventListener:vi.fn()};stream={getTracks:()=>[track],getVideoTracks:()=>[track]};getUserMedia=vi.fn().mockResolvedValue(stream);
 Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia}});
 URL.createObjectURL=vi.fn(()=> 'blob:person-test');URL.revokeObjectURL=vi.fn();
 apiFetch.mockResolvedValue({ok:true,json:async()=>({status:'REVIEW_REQUIRED',cosine_similarity:.7,capture_source:'UPLOADED_PHOTO'})});
});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
function enable(){fireEvent.click(screen.getByLabelText('Enable optional person comparison'));}
function choose(){fireEvent.change(screen.getByLabelText('Upload consented test photo'),{target:{files:[new File(['image'],'person.png',{type:'image/png'})]}});}
it('does not request camera or comparison until officer opts in',()=>{
 render(<OptionalPersonCheck screening={screening} onResult={()=>{}}/>);expect(getUserMedia).not.toHaveBeenCalled();expect(apiFetch).not.toHaveBeenCalled();expect(screen.queryByRole('button',{name:'Open live camera'})).toBeNull();
 enable();expect(getUserMedia).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'Open live camera'}));expect(getUserMedia).toHaveBeenCalledWith(expect.objectContaining({audio:false}));
});
it('records a skip without using the camera',async()=>{
 const saved=vi.fn();apiFetch.mockResolvedValue({ok:true,json:async()=>({status:'SKIPPED'})});render(<OptionalPersonCheck screening={screening} onResult={saved}/>);
 fireEvent.click(screen.getByRole('button',{name:'Skip person check'}));await waitFor(()=>expect(saved).toHaveBeenCalledWith({status:'SKIPPED'}));expect(getUserMedia).not.toHaveBeenCalled();expect(apiFetch.mock.calls[0][0]).toBe('/api/screening/SCR-PERSON/face/skip');
});
it('previews before sending, labels uploads correctly and clears the image after saving',async()=>{
 const saved=vi.fn();render(<OptionalPersonCheck screening={screening} onResult={saved}/>);enable();choose();
 expect(screen.getByAltText('Person capture awaiting comparison')).toBeTruthy();expect(apiFetch).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'Compare locally'}));
 await waitFor(()=>expect(saved).toHaveBeenCalled());expect(apiFetch.mock.calls[0][1].body.get('capture_source')).toBe('UPLOADED_PHOTO');expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:person-test');
});
it('cancels a pending comparison and ignores its late result',async()=>{
 let finish;apiFetch.mockImplementation(()=>new Promise(r=>finish=r));const saved=vi.fn();render(<OptionalPersonCheck screening={screening} onResult={saved}/>);enable();choose();fireEvent.click(screen.getByRole('button',{name:'Compare locally'}));
 fireEvent.click(screen.getByRole('button',{name:'Cancel comparison'}));expect(apiFetch.mock.calls[0][1].signal.aborted).toBe(true);
 await act(async()=>finish({ok:true,json:async()=>({status:'REVIEW_REQUIRED'})}));expect(saved).not.toHaveBeenCalled();expect(screen.getByLabelText('Enable optional person comparison').disabled).toBe(false);
});
it('keeps preview and allows retry after backend error',async()=>{
 apiFetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'Local model unavailable'})});render(<OptionalPersonCheck screening={screening} onResult={()=>{}}/>);enable();choose();fireEvent.click(screen.getByRole('button',{name:'Compare locally'}));
 expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.getByRole('button',{name:'Compare locally'}).disabled).toBe(false);expect(screen.getByAltText('Person capture awaiting comparison')).toBeTruthy();
});
it('camera permission denial offers retry and closes cleanly',async()=>{
 getUserMedia.mockRejectedValueOnce({name:'NotAllowedError'});const cancel=vi.fn();render(<LiveCameraCapture onCapture={()=>{}} onCancel={cancel}/>);
 await screen.findByText(/Camera permission denied/);fireEvent.click(screen.getByRole('button',{name:'Retry camera'}));await waitFor(()=>expect(getUserMedia).toHaveBeenCalledTimes(2));
 fireEvent.click(screen.getByRole('button',{name:'Close camera'}));expect(stop).toHaveBeenCalled();expect(cancel).toHaveBeenCalled();
});
it('stops a stream that resolves after leaving the camera view',async()=>{
 let finish;getUserMedia.mockImplementation(()=>new Promise(r=>finish=r));const rendered=render(<LiveCameraCapture onCapture={()=>{}} onCancel={()=>{}}/>);rendered.unmount();await act(async()=>finish(stream));expect(stop).toHaveBeenCalled();
});
it('captures a ready video frame and stops camera before preview',async()=>{
 const capture=vi.fn();vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({drawImage:vi.fn()});vi.spyOn(HTMLCanvasElement.prototype,'toBlob').mockImplementation(callback=>callback(new Blob(['pixels'],{type:'image/jpeg'})));
 render(<LiveCameraCapture onCapture={capture} onCancel={()=>{}}/>);await waitFor(()=>expect(document.querySelector('video').srcObject).toBe(stream));
 const video=document.querySelector('video');Object.defineProperty(video,'videoWidth',{value:1280});Object.defineProperty(video,'videoHeight',{value:720});fireEvent.loadedData(video);fireEvent.click(screen.getByRole('button',{name:'Capture person'}));
 expect(capture).toHaveBeenCalledWith(expect.any(File));expect(stop).toHaveBeenCalled();
});
it('does not provide skip as a way to erase a previous comparison',()=>{
 render(<OptionalPersonCheck screening={{...screening,result:{ai_analysis:{face:{status:'INCONCLUSIVE'}}}}} onResult={()=>{}}/>);expect(screen.queryByRole('button',{name:'Skip person check'})).toBeNull();
});
