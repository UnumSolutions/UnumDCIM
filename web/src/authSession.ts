export type Role = 'viewer'|'operator'|'approver'|'admin';
export type VerifiedIdentity = {actor:string;tenant:string;sites:string[];role:Role};
type SessionBase = VerifiedIdentity & {key:string;signal:AbortSignal};
export type AuthSession = SessionBase & (
  {mode:'demo'} | {mode:'oidc';accessToken:()=>string;unauthorized:(rejectedToken:string)=>void}
);

export function createDemoSession(role:Role,signal=new AbortController().signal):AuthSession {
  const actor = role==='approver'?'Jordan':role==='admin'?'Admin':role==='viewer'?'Viewer':'Alex';
  return {mode:'demo',key:`demo:${role}`,actor,tenant:'demo',sites:[],role,signal};
}

export function identityKey(identity:VerifiedIdentity):string {
  return JSON.stringify([identity.actor,identity.tenant,identity.role,[...identity.sites].sort()]);
}

export function validateIdentity(value:unknown):VerifiedIdentity {
  if(!value || typeof value!=='object') throw new Error('The server did not confirm an identity.');
  const identity = value as Partial<VerifiedIdentity>;
  if(typeof identity.actor!=='string' || !identity.actor.trim()
    || typeof identity.tenant!=='string' || !identity.tenant.trim()
    || !['viewer','operator','approver','admin'].includes(identity.role??'')
    || !Array.isArray(identity.sites) || !identity.sites.length
    || !identity.sites.every(site=>typeof site==='string' && !!site.trim())) {
    throw new Error('The server did not confirm a permitted identity.');
  }
  return {actor:identity.actor,tenant:identity.tenant,role:identity.role!,sites:[...identity.sites]};
}

export function sessionHeaders(session:AuthSession):Record<string,string> {
  session.signal.throwIfAborted();
  if(session.mode==='demo') return {'X-Demo-Role':session.role};
  if(session.mode==='oidc') return {Authorization:`Bearer ${session.accessToken()}`};
  throw new Error('Authentication is not configured.');
}
