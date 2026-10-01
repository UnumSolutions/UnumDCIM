import {sessionHeaders,type AuthSession} from './authSession';

export class ApiError extends Error {
  constructor(message:string, public readonly status:number) {
    super(message);
    this.name = 'ApiError';
  }
}

export const API_TIMEOUT_MS = 10_000;
type ApiOptions = {signal?:AbortSignal;timeoutMs?:number;signals?:AbortSignal[]};

export async function jsonRequest<T>(path:string,init:RequestInit={},options:ApiOptions={}):Promise<T>{
  const controller = new AbortController();
  const signals = [...(options.signals??[]),...(options.signal?[options.signal]:[])];
  const abortHandlers = signals.map(signal=>()=>controller.abort(signal.reason));
  let rejectAborted!:(reason:unknown)=>void;
  const aborted = new Promise<never>((_,reject)=>{rejectAborted=reject});
  const onAbort = ()=>rejectAborted(controller.signal.reason);
  controller.signal.addEventListener('abort',onAbort,{once:true});
  signals.forEach((signal,index)=>{
    signal.addEventListener('abort',abortHandlers[index],{once:true});
    if(signal.aborted) abortHandlers[index]();
  });
  const timeout = setTimeout(()=>controller.abort(new Error('Request timed out')),options.timeoutMs??API_TIMEOUT_MS);
  const request = async()=>{
    controller.signal.throwIfAborted();
    const response = await fetch(path,{credentials:'same-origin',cache:'no-store',...init,signal:controller.signal});
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
    signals.forEach((signal,index)=>signal.removeEventListener('abort',abortHandlers[index]));
    controller.signal.removeEventListener('abort',onAbort);
  }
}

export async function api<T>(service:string,path:string,session:AuthSession,body?:unknown,options:ApiOptions={}):Promise<T>{
  let usedToken='';
  try {
    const authenticationHeaders=sessionHeaders(session);
    usedToken=authenticationHeaders.Authorization?.slice('Bearer '.length)??'';
    return await jsonRequest<T>(`/api/${service}/${path}`,{
      method:body===undefined?'GET':'POST',
      headers:{'Content-Type':'application/json',...authenticationHeaders},
      body:body===undefined?undefined:JSON.stringify(body),
    },{...options,signals:[session.signal,...(options.signals??[])]});
  } catch(error) {
    if(session.mode==='oidc' && error instanceof ApiError && error.status===401) session.unauthorized(usedToken);
    throw error;
  }
}
