import {InMemoryWebStorage,UserManager,WebStorageStateStore,type User,type UserManagerSettings} from 'oidc-client-ts';
import {api,jsonRequest} from './api';
import {validateAuthConfig,type AuthConfig} from './authConfig';
import {createDemoSession,identityKey,validateIdentity,type AuthSession,type Role} from './authSession';

type OidcConfig = Extract<AuthConfig,{mode:'oidc'}>;
export type AuthSnapshot = {status:'loading'|'signed_out'|'authenticated'|'error';session:AuthSession|null;error:string;mode:'demo'|'oidc'|null};
type Manager = Pick<UserManager,'signinRedirect'|'signinRedirectCallback'|'signoutRedirect'|'signoutRedirectCallback'|'signinSilent'|'removeUser'|'clearStaleState'|'events'>;
type Environment = {
  origin:string;href:()=>string;replaceUrl:(url:string)=>void;stateStorage:Storage;
  manager?:(settings:UserManagerSettings)=>Manager;
};

export function oidcSettings(config:OidcConfig,stateStorage:Storage):UserManagerSettings {
  return {
    authority:config.issuer,client_id:config.client_id,redirect_uri:config.redirect_uri,
    post_logout_redirect_uri:config.post_logout_redirect_uri,response_type:'code',response_mode:'query',
    scope:config.scope,acr_values:config.acr_values,disablePKCE:false,loadUserInfo:false,
    userStore:new WebStorageStateStore({store:new InMemoryWebStorage()}),
    stateStore:new WebStorageStateStore({store:stateStorage,prefix:'unum.oidc.state.'}),
    automaticSilentRenew:false,monitorSession:false,accessTokenExpiringNotificationTimeInSeconds:60,
    requestTimeoutInSeconds:10,silentRequestTimeoutInSeconds:10,staleStateAgeInSeconds:600,
  };
}

export function createAuthStore(environment:Environment) {
  let snapshot:AuthSnapshot = {status:'loading',session:null,error:'',mode:null};
  const listeners = new Set<()=>void>();
  let config:AuthConfig|null = null;
  let manager:Manager|null = null;
  let initialized:Promise<void>|null = null;
  let sessionController:AbortController|null = null;
  let verificationController:AbortController|null = null;
  let currentUser:User|null = null;
  let revision = 0;
  let renewing:Promise<void>|null = null;
  let expiryTimer:ReturnType<typeof setTimeout>|undefined;
  const publish = (next:AuthSnapshot)=>{snapshot=next;listeners.forEach(listener=>listener())};
  const purge = (message='')=>{
    revision += 1;
    clearTimeout(expiryTimer);
    sessionController?.abort();sessionController=null;
    verificationController?.abort();verificationController=null;
    currentUser=null;
    publish({status:'signed_out',session:null,error:message,mode:config?.mode??null});
  };
  const expire = (message='Your session has ended. Sign in again.')=>{
    purge(message);
    void manager?.removeUser().catch(()=>{});
  };
  const token = (user:User)=>{
    if(!user.access_token || user.token_type.toLowerCase()!=='bearer' || !user.expires_at
      || user.expires_at*1000<=Date.now()+5_000) throw new Error('The sign-in token has expired.');
    return user.access_token;
  };
  const acceptUser = async(user:User)=>{
    const attempt = ++revision;
    verificationController?.abort();
    const controller = verificationController = new AbortController();
    const provisional:AuthSession = {
      mode:'oidc',key:'verifying',actor:'',tenant:'',sites:[],role:'viewer',signal:controller.signal,
      accessToken:()=>token(user),unauthorized:()=>{},
    };
    const identity = validateIdentity(await api<unknown>('inventory','identity',provisional));
    if(attempt!==revision) return;
    token(user);
    verificationController=null;
    const key = identityKey(identity);
    let session = snapshot.session;
    if(!session || session.key!==key) {
      sessionController?.abort();
      sessionController = new AbortController();
      const activeController=sessionController;
      session = {...identity,mode:'oidc',key,signal:sessionController.signal,
        accessToken:()=>{
          try {if(!currentUser) throw new Error('Sign in to continue.');return token(currentUser)}
          catch(error){expire();throw error}
        },unauthorized:rejectedToken=>{
          if(!activeController.signal.aborted && currentUser?.access_token===rejectedToken) {
            expire('The server no longer accepts this session. Sign in again.');
          }
        },
      };
    }
    currentUser=user;
    clearTimeout(expiryTimer);
    expiryTimer=setTimeout(()=>expire(),Math.max(0,user.expires_at!*1000-Date.now()-5_000));
    publish({status:'authenticated',session,error:'',mode:'oidc'});
  };
  const renew = ()=>{
    if(renewing) return renewing;
    if(!currentUser) return Promise.resolve();
    if(!currentUser.refresh_token || !manager) {expire('Your session needs a fresh sign-in.');return Promise.resolve()}
    let expectedRevision = revision;
    renewing=(async()=>{
      try {
        const user = await manager!.signinSilent();
        if(expectedRevision!==revision) {
          // signinSilent stores its result before resolving. A logout/expiry
          // during renewal must also remove that late manager-level token.
          await manager!.removeUser();
          return;
        }
        if(!user) throw new Error('Session renewal was not confirmed.');
        expectedRevision=revision+1;
        await acceptUser(user);
      } catch {
        if(expectedRevision===revision) expire('Session renewal failed. Sign in again.');
      } finally {renewing=null}
    })();
    return renewing;
  };
  const initialize = ()=>initialized??(initialized=(async()=>{
    try {
      config=validateAuthConfig(await jsonRequest<unknown>('/auth/config',{headers:{Accept:'application/json'}}),environment.origin);
      if(config.mode==='demo') {
        sessionController=new AbortController();
        publish({status:'authenticated',session:createDemoSession('operator',sessionController.signal),error:'',mode:'demo'});
        return;
      }
      manager=(environment.manager??(settings=>new UserManager(settings)))(oidcSettings(config,environment.stateStorage));
      manager.events.addAccessTokenExpiring(()=>{void renew()});
      manager.events.addAccessTokenExpired(()=>expire());
      manager.events.addUserSignedOut(()=>expire('Your identity provider session ended. Sign in again.'));
      manager.events.addSilentRenewError(()=>expire('Session renewal failed. Sign in again.'));
      await manager.clearStaleState();
      const url = new URL(environment.href());
      if(url.pathname===new URL(config.redirect_uri).pathname) {
        try {await acceptUser(await manager.signinRedirectCallback(url.href))}
        finally {environment.replaceUrl('/')}
      } else if(url.pathname===new URL(config.post_logout_redirect_uri).pathname && url.searchParams.has('state')) {
        try {await manager.signoutRedirectCallback(url.href);purge()}
        finally {environment.replaceUrl('/')}
      } else {
        publish({status:'signed_out',session:null,error:'',mode:'oidc'});
      }
    } catch {
      purge();
      await manager?.removeUser().catch(()=>{});
      publish({status:config?.mode==='oidc'?'signed_out':'error',session:null,
        error:config?.mode==='oidc'?'Sign-in could not be verified. Try signing in again.':'Sign-in configuration is unavailable or invalid. Contact your administrator.',
        mode:config?.mode??null});
    }
  })());
  return {
    getSnapshot:()=>snapshot,
    subscribe:(listener:()=>void)=>{listeners.add(listener);return()=>{listeners.delete(listener)}},
    initialize,
    signIn:async()=>{
      if(config?.mode!=='oidc' || !manager) return;
      purge();
      publish({...snapshot,status:'loading'});
      try {
        await manager.signinRedirect({nonce:crypto.randomUUID(),acr_values:config.acr_values,max_age:0,
          extraQueryParams:{kc_idp_hint:config.google_provider},state:{returnTo:'/'}});
      } catch {expire('Unable to start sign-in. Try again.')}
    },
    signOut:async()=>{
      if(config?.mode!=='oidc' || !manager) return;
      const idTokenHint=currentUser?.id_token;
      // Purge application state first; keep the manager's in-memory ID token
      // until it constructs the correlated provider logout request.
      purge();
      try {await manager.signoutRedirect({state:{returnTo:'/'},id_token_hint:idTokenHint})}
      catch {expire('You are signed out of this app. Identity provider logout could not be completed.')}
    },
    selectDemoRole:(role:Role)=>{
      if(config?.mode!=='demo') return;
      purge();sessionController=new AbortController();
      publish({status:'authenticated',session:createDemoSession(role,sessionController.signal),error:'',mode:'demo'});
    },
    renew,
  };
}
