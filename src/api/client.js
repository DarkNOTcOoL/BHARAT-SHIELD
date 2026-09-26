export const API_BASE_URL = '/api';
export async function apiFetch(url,options={}) {
  const target=new URL(url,window.location.origin);
  if(target.origin!==window.location.origin) throw new Error('External API requests are disabled.');
  const response=await fetch(target.href,{...options,credentials:'same-origin',headers:{...options.headers,'X-Local-Request':'1'}});
  if(response.status===401&&!target.pathname.endsWith('/auth/login')) window.dispatchEvent(new Event('session-expired'));
  return response;
}
