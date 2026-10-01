import {api} from './api';
import {contractCompatible} from './domain';
import type {Asset, Change, Scene, SyncState} from './types';
import type {AuthSession} from './authSession';

export type ModuleItem = {id:string;status:string;version:string};
type Service = 'placement' | 'inventory' | 'workflow' | 'synchronization' | 'registry';
export type ServiceStatus = {fetchedAt:number;error:string;loading:boolean};
export type ChangeHistory = {page:number;nextCursor:string|null;hasMore:boolean};
type ChangesResponse = {
  items:Change[];
  history:{limit:number;next_cursor:string|null;has_more:boolean};
};
export type OperationsData = {
  scene:Scene|null;
  assets:Asset[];
  changes:Change[];
  changeHistory:ChangeHistory;
  sync:SyncState|null;
  modules:ModuleItem[];
  status:Record<Service, ServiceStatus>;
};

const serviceLabels:Record<Service, string> = {
  placement:'Placement', inventory:'Inventory', workflow:'Workflow',
  synchronization:'Synchronization', registry:'Module registry',
};
const services = Object.keys(serviceLabels) as Service[];

function initialData():OperationsData {
  return {
    scene:null, assets:[], changes:[], changeHistory:{page:1,nextCursor:null,hasMore:false}, sync:null, modules:[],
    status:Object.fromEntries(services.map(service=>[
      service, {fetchedAt:0,error:'',loading:false},
    ])) as Record<Service, ServiceStatus>,
  };
}

/** One identity's data. Services publish independently within the latest refresh. */
export function createOperationsData(session:AuthSession) {
  let snapshot = initialData();
  let generation = 0;
  let controller:AbortController|null = null;
  let historyCursors:(string|null)[] = [null];
  let historyPage = 0;
  const listeners = new Set<()=>void>();
  const publish = (next:OperationsData) => {
    snapshot = next;
    listeners.forEach(listener=>listener());
  };
  const invalidate = ()=>{
    generation += 1;controller?.abort();controller=null;
    historyCursors=[null];historyPage=0;
    publish(initialData());
  };
  session.signal.addEventListener('abort',invalidate,{once:true});
  const refresh = async()=>{
    if(session.signal.aborted) return;
    const requestGeneration = ++generation;
    controller?.abort();
    const requestController = new AbortController();
    controller = requestController;
    const options = {signal:requestController.signal};
    const requestedPage = historyPage;
    const historyCursor = historyCursors[requestedPage];
    publish({...snapshot,status:Object.fromEntries(services.map(service=>[
      service,{...snapshot.status[service],loading:true},
    ])) as OperationsData['status']});
    const update = async(service:Service,request:()=>Promise<Partial<OperationsData>>)=>{
      try {
        const data = await request();
        if(requestGeneration!==generation) return;
        publish({...snapshot,...data,status:{...snapshot.status,
          [service]:{fetchedAt:Date.now(),error:'',loading:false},
        }});
      } catch {
        if(requestGeneration!==generation) return;
        if(service==='workflow') historyPage = snapshot.changeHistory.page-1;
        publish({...snapshot,status:{...snapshot.status,[service]:{
          ...snapshot.status[service],
          error:`${serviceLabels[service]} unavailable${service==='placement'?' or incompatible':''}`,loading:false,
        }}});
      }
    };
    await Promise.all([
      update('placement',async()=>{
        const scene = await api<Scene>('placement','scene',session,undefined,options);
        if(!contractCompatible(scene.contract,'unum.scene/1')) throw new Error('Incompatible placement contract');
        return {scene};
      }),
      update('inventory',async()=>({assets:(await api<{items:Asset[]}>('inventory','assets',session,undefined,options)).items})),
      update('workflow',async()=>{
        const path = historyCursor?`changes?history_cursor=${encodeURIComponent(historyCursor)}`:'changes';
        const changes = await api<ChangesResponse>('workflow',path,session,undefined,options);
        return {changes:changes.items,changeHistory:{page:requestedPage+1,
          nextCursor:changes.history.next_cursor,hasMore:changes.history.has_more,
        }};
      }),
      update('synchronization',async()=>({sync:await api<SyncState>('synchronization','status',session,undefined,options)})),
      update('registry',async()=>({modules:(await api<{items:ModuleItem[]}>('registry','modules',session,undefined,options)).items})),
    ]);
    if(controller===requestController) controller = null;
  };
  return {
    getSnapshot:()=>snapshot,
    subscribe:(listener:()=>void)=>{
      listeners.add(listener);
      return ()=>{listeners.delete(listener)};
    },
    // Invalidates pending requests during identity changes and effect cleanup.
    invalidate,
    refresh,
    olderChanges:async()=>{
      if(snapshot.status.workflow.loading || !snapshot.changeHistory.hasMore || !snapshot.changeHistory.nextCursor) return;
      historyCursors = [...historyCursors.slice(0,historyPage+1),snapshot.changeHistory.nextCursor];
      historyPage += 1;
      await refresh();
    },
    newerChanges:async()=>{
      if(snapshot.status.workflow.loading || historyPage===0) return;
      historyPage -= 1;
      await refresh();
    },
  };
}
