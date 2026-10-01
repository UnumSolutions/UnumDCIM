import React from 'react';
import {createRoot} from 'react-dom/client';
import AuthRoot from './AuthRoot';
import {createAuthStore} from './authStore';
import './style.css';
const auth = createAuthStore({origin:window.location.origin,href:()=>window.location.href,
  replaceUrl:url=>window.history.replaceState(null,'',url),get stateStorage(){return window.sessionStorage}});
createRoot(document.getElementById('root')!).render(<React.StrictMode><AuthRoot store={auth}/></React.StrictMode>);
