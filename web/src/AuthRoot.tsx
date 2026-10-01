import {useEffect,useSyncExternalStore} from 'react';
import App from './App';
import type {createAuthStore} from './authStore';

export default function AuthRoot({store}:{store:ReturnType<typeof createAuthStore>}) {
  const auth = useSyncExternalStore(store.subscribe,store.getSnapshot,store.getSnapshot);
  useEffect(()=>{void store.initialize()},[store]);
  if(auth.status==='authenticated' && auth.session) {
    return <App key={auth.session.key} session={auth.session} onDemoRoleChange={store.selectDemoRole}
      onSignOut={()=>void store.signOut()}/>;
  }
  return <main className="sign-in-page"><section className="sign-in-card" aria-label="UnumDCIM sign-in">
    <div className="wordmark">unum<span>DCIM</span></div>
    <h1>{auth.status==='loading'?'Connecting securely…':'Sign in to your workspace'}</h1>
    {auth.error&&<p className="alert error" role="alert">{auth.error}</p>}
    {auth.mode==='oidc'&&auth.status!=='loading'&&<>
      <p>Use your work Google account to continue. Your organization verifies access and requires multifactor authentication.</p>
      <button className="button primary" onClick={()=>void store.signIn()}>Sign in with Google</button>
    </>}
    {auth.status==='loading'&&<p role="status">Checking sign-in configuration and access permissions.</p>}
  </section></main>;
}
