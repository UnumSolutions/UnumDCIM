import {api} from './api';
import {contractCompatible} from './domain';
import type {Asset, Change, Scene, SyncState} from './types';

export type ModuleItem = {id:string;status:string;version:string};
type Service = 'placement' | 'inventory' | 'workflow' | 'synchronization' | 'registry';
export type ServiceStatus = {fetchedAt:number;error:string;loading:boolean};
export type OperationsData = {
  scene:Scene|null;
  assets:Asset[];
  changes:Change[];
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
    scene:null, assets:[], changes:[], sync:null, modules:[],
    status:Object.fromEntries(services.map(service=>[
      service, {fetchedAt:0,error:'',loading:false},
    ])) as Record<Service, ServiceStatus>,
  };
}

/** One identity's data. Only the most recently started refresh may publish. */
export function createOperationsData(role:string) {
  let snapshot = initialData();
  let generation = 0;
  const listeners = new Set<()=>void>();
  const publish = (next:OperationsData) => {
    snapshot = next;
    listeners.forEach(listener=>listener());
  };
  return {
    getSnapshot:()=>snapshot,
    subscribe:(listener:()=>void)=>{
      listeners.add(listener);
      return ()=>{listeners.delete(listener)};
    },
    // Invalidates pending requests during identity changes and effect cleanup.
    invalidate:()=>{generation += 1},
    refresh:async()=>{
      const requestGeneration = ++generation;
      publish({...snapshot,status:Object.fromEntries(services.map(service=>[
        service,{...snapshot.status[service],loading:true},
      ])) as OperationsData['status']});
      const results = await Promise.allSettled([
        api<Scene>('placement','scene',role).then(scene=>{
          if(!contractCompatible(scene.contract,'unum.scene/1')) {
            throw new Error('Incompatible placement contract');
          }
          return scene;
        }),
        api<{items:Asset[]}>('inventory','assets',role),
        api<{items:Change[]}>('workflow','changes',role),
        api<SyncState>('synchronization','status',role),
        api<{items:ModuleItem[]}>('registry','modules',role),
      ]);
      if(requestGeneration !== generation) return;
      const fetchedAt = Date.now();
      const [scene,assets,changes,sync,modules] = results;
      publish({
        scene:scene.status==='fulfilled'?scene.value:snapshot.scene,
        assets:assets.status==='fulfilled'?assets.value.items:snapshot.assets,
        changes:changes.status==='fulfilled'?changes.value.items:snapshot.changes,
        sync:sync.status==='fulfilled'?sync.value:snapshot.sync,
        modules:modules.status==='fulfilled'?modules.value.items:snapshot.modules,
        status:Object.fromEntries(services.map((service,index)=>[
          service,results[index].status==='fulfilled'
            ?{fetchedAt,error:'',loading:false}
            :{...snapshot.status[service],error:`${serviceLabels[service]} unavailable${service==='placement'?' or incompatible':''}`,loading:false},
        ])) as OperationsData['status'],
      });
    },
  };
}
