import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {afterEach,describe,expect,it,vi} from 'vitest';
import App from './App';
import {createDemoSession,type AuthSession} from './authSession';

afterEach(()=>{vi.unstubAllGlobals()});
function render(session:AuthSession) {
  vi.stubGlobal('localStorage',{getItem:()=>null});
  vi.stubGlobal('matchMedia',()=>({matches:false}));
  return renderToStaticMarkup(<App session={session} onDemoRoleChange={()=>{}} onSignOut={()=>{}}/>);
}
describe('authenticated application shell',()=>{
  it('shows the verified principal and sign-out control without demo identity switching or synthetic branding',()=>{
    const html=render({mode:'oidc',key:'verified-key',actor:'oidc:verified-staff',tenant:'tenant-one',sites:['site-one'],role:'viewer',
      signal:new AbortController().signal,accessToken:()=>{throw new Error('SSR must not access tokens')},unauthorized:()=>{}});
    expect(html).toContain('oidc:verified-staff');
    expect(html).toContain('viewer');
    expect(html).toContain('Sign out');
    expect(html).not.toContain('Demo operator identity');
    expect(html).not.toContain('SYNTHETIC DEMO');
    expect(html).not.toContain('synthetic data only');
  });
  it('retains the identity selector only for an explicit demo session',()=>{
    const html=render(createDemoSession('operator'));
    expect(html).toContain('Demo operator identity');
    expect(html).toContain('SYNTHETIC DEMO');
    expect(html).not.toContain('Sign out');
  });
});
