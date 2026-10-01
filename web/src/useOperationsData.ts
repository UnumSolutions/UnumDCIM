import {useEffect, useMemo, useSyncExternalStore} from 'react';
import {createOperationsData} from './operationsData';
import type {AuthSession} from './authSession';

export function useOperationsData(session:AuthSession) {
  const store = useMemo(()=>createOperationsData(session),[session]);
  const data = useSyncExternalStore(store.subscribe,store.getSnapshot,store.getSnapshot);
  useEffect(()=>{
    let active = true;
    let timer:ReturnType<typeof setTimeout>;
    const poll = async()=>{
      // Slow polling must not continually supersede its own pending requests.
      if(!Object.values(store.getSnapshot().status).some(status=>status.loading)) {
        await store.refresh();
      }
      if(active) timer = setTimeout(()=>{void poll()},15000);
    };
    void store.refresh().then(()=>{if(active) timer = setTimeout(()=>{void poll()},15000)});
    return ()=>{
      active = false;
      clearTimeout(timer);
      store.invalidate();
    };
  },[store]);
  return {...data,refresh:store.refresh,olderChanges:store.olderChanges,newerChanges:store.newerChanges};
}
