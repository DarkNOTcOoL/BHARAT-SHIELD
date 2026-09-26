import {useEffect,useState} from 'react';
import {apiFetch} from '../api/client';

export async function requestJSON(path,options={}){
 const response=await apiFetch(path,options);
 const data=await response.json().catch(()=>null);
 if(!response.ok)throw Error(typeof data?.detail==='string'?data.detail:`Local request failed (${response.status}). Please retry.`);
 if(data===null)throw Error('The local server returned an unreadable response.');
 return data;
}
export function useLocalResource(path,revision=0){
 const [state,setState]=useState({data:null,loading:true,error:''});
 useEffect(()=>{
  if(!path){setState({data:null,loading:false,error:''});return;}
  const controller=new AbortController();let active=true;
  setState({data:null,loading:true,error:''});
  const timeout=setTimeout(()=>{controller.abort();if(active)setState({data:null,loading:false,error:'Local request timed out. Retry when the server is ready.'});},30000);
  requestJSON(path,{signal:controller.signal}).then(data=>{if(active)setState({data,loading:false,error:''});}).catch(e=>{if(active&&!controller.signal.aborted)setState({data:null,loading:false,error:e.message});}).finally(()=>clearTimeout(timeout));
  return()=>{active=false;clearTimeout(timeout);controller.abort();};
 },[path,revision]);
 return state;
}
