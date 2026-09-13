import {afterEach, describe, expect, it, vi} from 'vitest';
import {createOperationsData} from './operationsData';
import type {Scene} from './types';

type PendingRequest = {
  path:string;
  role:string;
  resolve:(response:Response)=>void;
  reject:(error:Error)=>void;
};
function controlledNetwork() {
  const requests:PendingRequest[] = [];
  vi.stubGlobal('fetch',vi.fn((path:string,options:RequestInit)=>new Promise<Response>((resolve,reject)=>{
    requests.push({path,role:(options.headers as Record<string,string>)['X-Demo-Role'],resolve,reject});
  })));
  return requests;
}
function scene(revision:number):Scene {
  return {contract:'unum.scene/1',generated_at:'2026-09-13T12:00:00Z',rooms:[],racks:[],authority:[],
    placements:[{asset_id:'asset-1',rack_id:'rack-1',u:revision,height_u:1,face:'front',owner:'unum',revision}]};
}
function finish(requests:PendingRequest[], revision:number, failures:string[]=[]) {
  for(const request of requests) {
    if(failures.some(service=>request.path.includes(`/api/${service}/`))) {
      request.reject(new TypeError('Connection lost'));
    } else {
      const value = request.path.includes('/placement/')?scene(revision)
        :request.path.includes('/synchronization/')?{live_write_enabled:false,connections:[],conflicts:[]}
        :{items:[]};
      request.resolve(Response.json(value));
    }
  }
}
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks()});

describe('operations refresh requests',()=>{
  it('does not let a delayed earlier batch replace a newer placement or freshness result',async()=>{
    const requests = controlledNetwork();
    const clock = vi.spyOn(Date,'now').mockReturnValue(1000);
    const store = createOperationsData('operator');
    const older = store.refresh();
    const newer = store.refresh();
    finish(requests.slice(5),2);
    await newer;
    const accepted = store.getSnapshot();
    expect(accepted.scene?.placements[0].revision).toBe(2);
    expect(accepted.status.placement).toEqual({fetchedAt:1000,error:'',loading:false});
    clock.mockReturnValue(2000);
    finish(requests.slice(0,5),1);
    await older;
    expect(store.getSnapshot()).toBe(accepted);
  });

  it('retains a newer failure when an older successful request finally arrives',async()=>{
    const requests = controlledNetwork();
    const store = createOperationsData('operator');
    const initial = store.refresh();
    finish(requests,1);
    await initial;
    const lastSuccessful = store.getSnapshot().status.placement.fetchedAt;
    const older = store.refresh();
    const newer = store.refresh();
    finish(requests.slice(10),3,['placement']);
    await newer;
    finish(requests.slice(5,10),2);
    await older;
    expect(store.getSnapshot().scene?.placements[0].revision).toBe(1);
    expect(store.getSnapshot().status.placement.error).toMatch('unavailable');
    expect(store.getSnapshot().status.placement.fetchedAt).toBe(lastSuccessful);
  });

  it('tracks service failures and recovery independently without clearing retained data',async()=>{
    const requests = controlledNetwork();
    const clock = vi.spyOn(Date,'now').mockReturnValue(1000);
    const store = createOperationsData('operator');
    const initial = store.refresh();
    finish(requests,1);
    await initial;
    clock.mockReturnValue(2000);
    const partial = store.refresh();
    finish(requests.slice(5),2,['workflow','registry']);
    await partial;
    expect(store.getSnapshot().scene?.placements[0].revision).toBe(2);
    expect(store.getSnapshot().status.placement).toEqual({fetchedAt:2000,error:'',loading:false});
    expect(store.getSnapshot().status.workflow).toEqual({fetchedAt:1000,error:'Workflow unavailable',loading:false});
    expect(store.getSnapshot().status.registry.error).toBe('Module registry unavailable');
    clock.mockReturnValue(3000);
    const recovery = store.refresh();
    finish(requests.slice(10),3);
    await recovery;
    expect(store.getSnapshot().status.workflow).toEqual({fetchedAt:3000,error:'',loading:false});
  });

  it('rejects incompatible scene contracts without marking placement fresh',async()=>{
    const requests = controlledNetwork();
    const store = createOperationsData('operator');
    const refresh = store.refresh();
    requests[0].resolve(Response.json({...scene(1),contract:'unum.scene/2'}));
    finish(requests.slice(1),1);
    await refresh;
    expect(store.getSnapshot().scene).toBeNull();
    expect(store.getSnapshot().status.placement.fetchedAt).toBe(0);
    expect(store.getSnapshot().status.placement.error).toMatch('incompatible');
    expect(store.getSnapshot().status.inventory.error).toBe('');
  });

  it('invalidates in-flight updates on cleanup and gives a new identity an empty snapshot',async()=>{
    const requests = controlledNetwork();
    const operator = createOperationsData('operator');
    const refresh = operator.refresh();
    operator.invalidate();
    const approver = createOperationsData('approver');
    expect(approver.getSnapshot().scene).toBeNull();
    const approverRefresh = approver.refresh();
    expect(requests.slice(5).every(request=>request.role==='approver')).toBe(true);
    finish(requests.slice(5),2);
    await approverRefresh;
    finish(requests.slice(0,5),1);
    await refresh;
    expect(operator.getSnapshot().scene).toBeNull();
    expect(approver.getSnapshot().scene?.placements[0].revision).toBe(2);
    // React development effect replay may reuse a store after cleanup.
    const replay = operator.refresh();
    finish(requests.slice(10),3);
    await replay;
    expect(operator.getSnapshot().scene?.placements[0].revision).toBe(3);
  });
});
