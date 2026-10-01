export class ApiError extends Error {
  constructor(message:string, public readonly status:number) {
    super(message);
    this.name = 'ApiError';
  }
}

export const API_TIMEOUT_MS = 10_000;
type ApiOptions = {signal?:AbortSignal;timeoutMs?:number};

export async function api<T>(service:string,path:string,role:string,body?:unknown,options:ApiOptions={}):Promise<T>{
  const controller = new AbortController();
  const abortFromCaller = ()=>controller.abort(options.signal?.reason);
  let rejectAborted!:(reason:unknown)=>void;
  const aborted = new Promise<never>((_,reject)=>{rejectAborted=reject});
  const onAbort = ()=>rejectAborted(controller.signal.reason);
  controller.signal.addEventListener('abort',onAbort,{once:true});
  options.signal?.addEventListener('abort',abortFromCaller,{once:true});
  if(options.signal?.aborted) abortFromCaller();
  const timeout = setTimeout(()=>controller.abort(new Error(`${service} request timed out`)),options.timeoutMs??API_TIMEOUT_MS);
  const request = async()=>{
    controller.signal.throwIfAborted();
    const response = await fetch(`/api/${service}/${path}`,{
      method:body===undefined?'GET':'POST',
      headers:{'Content-Type':'application/json','X-Demo-Role':role},
      body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal,
    });
    if(!response.ok) {
      const content:unknown = await response.json().catch(()=>null);
      const message = content && typeof content==='object' && 'error' in content && typeof content.error==='string'
        ?content.error:'Request failed';
      throw new ApiError(message,response.status);
    }
    // A successful status is not an acknowledgement if its body was lost.
    // Preserve parsing/transport failures so callers can retry the same command.
    return await response.json() as T;
  };
  try {
    // Race explicitly as well as aborting fetch, so even a stalled transport or
    // response body cannot keep a refresh/action pending beyond its deadline.
    return await Promise.race([request(),aborted]);
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort',abortFromCaller);
    controller.signal.removeEventListener('abort',onAbort);
  }
}
