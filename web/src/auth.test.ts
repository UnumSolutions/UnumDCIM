import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {InMemoryWebStorage,User,type UserManager,type UserManagerSettings} from 'oidc-client-ts';
import {api} from './api';
import {validateAuthConfig,type AuthConfig} from './authConfig';
import {createAuthStore,oidcSettings} from './authStore';
import {createDemoSession,identityKey,type VerifiedIdentity} from './authSession';
import {createOperationsData} from './operationsData';

const origin='https://dcim.example.test';
const config:Extract<AuthConfig,{mode:'oidc'}>={mode:'oidc',issuer:'https://identity.example.test/realms/unum',
  client_id:'unum-web',redirect_uri:`${origin}/auth/callback`,post_logout_redirect_uri:`${origin}/auth/logout/callback`,
  scope:'openid profile email unum.api',acr_values:'urn:unum:acr:staff-mfa',google_provider:'google'};
const verified:VerifiedIdentity={actor:'oidc:verified-alex',tenant:'tenant-a',sites:['site-a'],role:'operator'};
function user(token='access-one',expiresIn=300,refreshToken:string|undefined='refresh-one') {
  return new User({access_token:token,id_token:'id-token',refresh_token:refreshToken,token_type:'Bearer',
    expires_at:Math.floor(Date.now()/1000)+expiresIn,
    profile:{sub:'unverified-profile-subject',iss:config.issuer,aud:config.client_id,exp:Math.floor(Date.now()/1000)+300,iat:Math.floor(Date.now()/1000),role:'admin',tenant:'wrong-tenant'}});
}
function fixture(href=`${origin}/auth/callback?code=one-time-code&state=transaction`) {
  const callbacks:Record<string,()=>void>={};
  const events=Object.fromEntries(['AccessTokenExpiring','AccessTokenExpired','UserSignedOut','SilentRenewError']
    .map(name=>[`add${name}`,vi.fn((callback:()=>void)=>{callbacks[name]=callback;return()=>{delete callbacks[name]}})]));
  const manager={events,signinRedirect:vi.fn().mockResolvedValue(undefined),signinRedirectCallback:vi.fn().mockResolvedValue(user()),
    signoutRedirect:vi.fn().mockResolvedValue(undefined),signoutRedirectCallback:vi.fn().mockResolvedValue({}),
    signinSilent:vi.fn().mockResolvedValue(user('access-two')),removeUser:vi.fn().mockResolvedValue(undefined),clearStaleState:vi.fn().mockResolvedValue(undefined)};
  const storage=new InMemoryWebStorage();
  const replaceUrl=vi.fn();
  const settings:UserManagerSettings[]=[];
  let identity:unknown=verified;
  const fetch=vi.fn(async(path:string)=>{
    if(path==='/auth/config') return Response.json(config);
    if(path==='/api/inventory/identity') return Response.json(identity);
    return Response.json({items:[]});
  });
  vi.stubGlobal('fetch',fetch);
  const store=createAuthStore({origin,href:()=>href,replaceUrl,stateStorage:storage,
    manager:configuration=>{settings.push(configuration);return manager as unknown as UserManager}});
  return {store,manager,callbacks,storage,replaceUrl,settings,fetch,setIdentity:(value:unknown)=>{identity=value}};
}
beforeEach(()=>{vi.useFakeTimers();vi.setSystemTime(new Date('2026-09-30T12:00:00Z'))});
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();vi.restoreAllMocks()});

describe('public authentication configuration',()=>{
  it('requires an explicit mode and rejects insecure or off-origin OIDC settings',()=>{
    expect(validateAuthConfig({mode:'demo'},'http://127.0.0.1:8080')).toEqual({mode:'demo'});
    for(const invalid of [{},null,{...config,issuer:'http://identity.example.test'},
      {...config,redirect_uri:'https://other.example.test/auth/callback'},
      {...config,post_logout_redirect_uri:'https://other.example.test/'},
      {...config,scope:'openid'},{...config,acr_values:'password-only'}]) {
      expect(()=>validateAuthConfig(invalid,origin)).toThrow();
    }
    expect(()=>validateAuthConfig(config,'http://dcim.example.test')).toThrow();
  });
  it('fails closed when the configuration request fails; no demo or API requests follow',async()=>{
    const f=fixture();
    f.fetch.mockRejectedValue(new TypeError('Network unavailable'));
    await f.store.initialize();
    expect(f.store.getSnapshot()).toMatchObject({status:'error',session:null,mode:null});
    expect(f.fetch).toHaveBeenCalledTimes(1);
    expect(f.manager.signinRedirectCallback).not.toHaveBeenCalled();
  });
  it('keeps bearer tokens in memory while redirect transaction state can survive navigation',async()=>{
    const storage=new InMemoryWebStorage();
    const settings=oidcSettings(config,storage);
    await settings.userStore!.set('user','access-and-refresh-tokens');
    expect(storage.length).toBe(0);
    await settings.stateStore!.set('transaction','pkce-verifier');
    expect(storage.length).toBe(1);
    expect(storage.getItem('unum.oidc.state.transaction')).toBe('pkce-verifier');
    expect(settings).toMatchObject({response_type:'code',disablePKCE:false,automaticSilentRenew:false});
  });
});

describe('verified browser identity',()=>{
  it('processes callbacks once and uses only the backend identity for role and tenant',async()=>{
    const f=fixture();
    const first=f.store.initialize();
    expect(f.store.initialize()).toBe(first);
    await first;
    expect(f.manager.signinRedirectCallback).toHaveBeenCalledTimes(1);
    expect(f.replaceUrl).toHaveBeenCalledWith('/');
    expect(f.store.getSnapshot().session).toMatchObject({...verified,mode:'oidc',key:identityKey(verified)});
    const identityRequest=f.fetch.mock.calls.find(([path])=>path==='/api/inventory/identity');
    expect(identityRequest).toBeDefined();
    const options=(f.fetch.mock.calls as unknown as [string,RequestInit][]).find(([path])=>path==='/api/inventory/identity')![1];
    expect(options.headers).toMatchObject({Authorization:'Bearer access-one'});
    expect(options.headers).not.toHaveProperty('X-Demo-Role');
  });
  it('rejects missing or invalid backend scope even when provider claims say admin',async()=>{
    const f=fixture();
    f.setIdentity({...verified,role:'service'});
    await f.store.initialize();
    expect(f.store.getSnapshot().session).toBeNull();
    expect(f.store.getSnapshot().error).toContain('could not be verified');
    expect(f.manager.removeUser).toHaveBeenCalled();
  });
  it('starts Google broker login with PKCE configuration, nonce, MFA ACR and fresh authentication',async()=>{
    const f=fixture(`${origin}/`);
    await f.store.initialize();
    expect(f.store.getSnapshot().status).toBe('signed_out');
    await f.store.signIn();
    expect(f.manager.signinRedirect).toHaveBeenCalledWith(expect.objectContaining({
      nonce:expect.any(String),acr_values:config.acr_values,max_age:0,extraQueryParams:{kc_idp_hint:'google'},
    }));
  });
  it('purges identity and cancels pending requests before provider logout',async()=>{
    const f=fixture();
    await f.store.initialize();
    const session=f.store.getSnapshot().session!;
    f.fetch.mockImplementation(()=>new Promise<Response>(()=>{}));
    const request=api('inventory','assets',session);
    const rejected=expect(request).rejects.toMatchObject({name:'AbortError'});
    await f.store.signOut();
    await rejected;
    expect(f.store.getSnapshot().session).toBeNull();
    expect(session.signal.aborted).toBe(true);
    expect(f.manager.signoutRedirect).toHaveBeenCalledWith({state:{returnTo:'/'},id_token_hint:'id-token'});
    expect(f.manager.removeUser).not.toHaveBeenCalled();
  });
  it('handles a correlated logout callback and removes response parameters',async()=>{
    const f=fixture(`${origin}/auth/logout/callback?state=logout-transaction`);
    await f.store.initialize();
    expect(f.manager.signoutRedirectCallback).toHaveBeenCalledTimes(1);
    expect(f.replaceUrl).toHaveBeenCalledWith('/');
    expect(f.store.getSnapshot()).toMatchObject({status:'signed_out',session:null});
  });
  it('uses only the demo header after an explicit demo configuration',async()=>{
    const f=fixture();
    f.fetch.mockResolvedValue(Response.json({mode:'demo'}));
    await f.store.initialize();
    const first=f.store.getSnapshot().session!;
    f.store.selectDemoRole('approver');
    expect(first.signal.aborted).toBe(true);
    f.fetch.mockResolvedValue(Response.json({items:[]}));
    await api('inventory','assets',f.store.getSnapshot().session!);
    const options=(f.fetch.mock.calls as unknown as [string,RequestInit][]).at(-1)![1];
    expect(options.headers).toMatchObject({'X-Demo-Role':'approver'});
    expect(options.headers).not.toHaveProperty('Authorization');
  });
});

describe('token renewal and expiry',()=>{
  it('verifies renewed tokens and cancels the previous identity even when its role is unchanged',async()=>{
    const f=fixture();
    await f.store.initialize();
    const first=f.store.getSnapshot().session!;
    f.setIdentity({...verified,actor:'oidc:verified-other',tenant:'tenant-b',sites:['site-b']});
    await f.store.renew();
    const next=f.store.getSnapshot().session!;
    expect(first.signal.aborted).toBe(true);
    expect(next.key).not.toBe(first.key);
    expect(next).toMatchObject({actor:'oidc:verified-other',tenant:'tenant-b',role:'operator'});
  });
  it('retains the same identity context on valid renewal but replaces its in-memory token',async()=>{
    const f=fixture();
    await f.store.initialize();
    const first=f.store.getSnapshot().session!;
    await f.store.renew();
    expect(f.store.getSnapshot().session).toBe(first);
    expect(first.signal.aborted).toBe(false);
    if(first.mode!=='oidc') throw new Error('Expected OIDC session');
    expect(first.accessToken()).toBe('access-two');
  });
  it('fails closed on refresh failure and never falls back to iframe login without a refresh token',async()=>{
    const f=fixture();
    const withoutRefresh=user();delete withoutRefresh.refresh_token;
    f.manager.signinRedirectCallback.mockResolvedValue(withoutRefresh);
    await f.store.initialize();
    await f.store.renew();
    expect(f.manager.signinSilent).not.toHaveBeenCalled();
    expect(f.store.getSnapshot().session).toBeNull();
    const g=fixture();
    await g.store.initialize();
    g.manager.signinSilent.mockRejectedValue(new Error('invalid_grant'));
    await g.store.renew();
    expect(g.store.getSnapshot().session).toBeNull();
    expect(g.store.getSnapshot().error).toContain('renewal failed');
  });
  it('expires the session and prevents sending a token after a suspended browser resumes',async()=>{
    const f=fixture();
    await f.store.initialize();
    const first=f.store.getSnapshot().session!;
    vi.setSystemTime(new Date('2026-09-30T12:06:00Z'));
    const count=f.fetch.mock.calls.length;
    await expect(api('inventory','assets',first)).rejects.toThrow('expired');
    expect(f.fetch).toHaveBeenCalledTimes(count);
    expect(first.signal.aborted).toBe(true);
    expect(f.store.getSnapshot().session).toBeNull();
  });
  it('purges the authenticated context at expiry even without another API request',async()=>{
    const f=fixture();
    f.manager.signinRedirectCallback.mockResolvedValue(user('short-lived',20));
    await f.store.initialize();
    const session=f.store.getSnapshot().session!;
    await vi.advanceTimersByTimeAsync(15_000);
    expect(f.store.getSnapshot().session).toBeNull();
    expect(session.signal.aborted).toBe(true);
  });
  it('does not restore identity when an in-flight renewal completes after logout',async()=>{
    const f=fixture();
    await f.store.initialize();
    let finish!:(value:User)=>void;
    f.manager.signinSilent.mockImplementation(()=>new Promise<User>(resolve=>{finish=resolve}));
    const renewal=f.store.renew();
    await f.store.signOut();
    finish(user('late-token'));
    await renewal;
    expect(f.store.getSnapshot().session).toBeNull();
    expect(f.manager.removeUser).toHaveBeenCalledTimes(1);
  });
  it('ignores a delayed 401 for an old token after successful same-identity renewal',async()=>{
    const f=fixture();
    await f.store.initialize();
    const session=f.store.getSnapshot().session!;
    let respond!:(response:Response)=>void;
    f.fetch.mockImplementationOnce(()=>new Promise<Response>(resolve=>{respond=resolve}));
    const oldRequest=api('inventory','assets',session);
    const rejected=expect(oldRequest).rejects.toMatchObject({status:401});
    await f.store.renew();
    respond(Response.json({error:'Expired token'},{status:401}));
    await rejected;
    expect(f.store.getSnapshot().session).toBe(session);
    expect(session.signal.aborted).toBe(false);
  });
  it('purges a session when the currently active token receives an unauthorized response',async()=>{
    const f=fixture();
    await f.store.initialize();
    const session=f.store.getSnapshot().session!;
    f.fetch.mockResolvedValue(Response.json({error:'Session revoked'},{status:401}));
    await expect(api('inventory','assets',session)).rejects.toMatchObject({status:401});
    expect(f.store.getSnapshot().session).toBeNull();
    expect(session.signal.aborted).toBe(true);
  });
  it('purges cached operations immediately when the authentication context ends',async()=>{
    const controller=new AbortController();
    const session=createDemoSession('operator',controller.signal);
    const f=fixture();
    f.fetch.mockImplementation(async(path:string)=>Response.json(path.includes('/placement/')
      ?{contract:'unum.scene/1',rooms:[],racks:[],placements:[],authority:[],generated_at:''}
      :path.includes('/workflow/')?{items:[],history:{limit:50,next_cursor:null,has_more:false}}
      :path.includes('/synchronization/')?{conflicts:[],connections:[],live_write_enabled:false}
      :{items:[{id:'private-data'}]}));
    const data=createOperationsData(session);
    await data.refresh();
    expect(data.getSnapshot().assets).toHaveLength(1);
    controller.abort();
    expect(data.getSnapshot().assets).toEqual([]);
    expect(data.getSnapshot().scene).toBeNull();
  });
});
