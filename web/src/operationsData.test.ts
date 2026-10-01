import {afterEach, describe, expect, it, vi} from 'vitest';
import {createOperationsData} from './operationsData';
import {API_TIMEOUT_MS} from './api';
import type {Change,Scene} from './types';

type PendingRequest = {
  path:string;
  role:string;
  signal:AbortSignal;
  resolve:(response:Response)=>void;
  reject:(error:Error)=>void;
};
function controlledNetwork() {
  const requests:PendingRequest[] = [];
  vi.stubGlobal('fetch',vi.fn((path:string,options:RequestInit)=>new Promise<Response>((resolve,reject)=>{
    requests.push({path,role:(options.headers as Record<string,string>)['X-Demo-Role'],signal:options.signal!,resolve,reject});
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
        :request.path.includes('/workflow/')?{items:[],history:{limit:50,next_cursor:null,has_more:false}}
        :{items:[]};
      request.resolve(Response.json(value));
    }
  }
}
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();vi.restoreAllMocks()});

describe('operations refresh requests',()=>{
  it('does not let a delayed earlier batch replace a newer placement or freshness result',async()=>{
    const requests = controlledNetwork();
    const clock = vi.spyOn(Date,'now').mockReturnValue(1000);
    const store = createOperationsData('operator');
    const older = store.refresh();
    const newer = store.refresh();
    expect(requests.slice(0,5).every(request=>request.signal.aborted)).toBe(true);
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
    expect(requests.every(request=>request.signal.aborted)).toBe(true);
    await refresh;
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

  it('publishes healthy services while another hangs, then settles its timeout without losing data',async()=>{
    vi.useFakeTimers();
    const requests = controlledNetwork();
    const store = createOperationsData('operator');
    const initial = store.refresh();
    finish(requests,1);
    await initial;
    const previousRegistry = store.getSnapshot().status.registry.fetchedAt;
    let finished = false;
    const refresh = store.refresh().then(()=>{finished=true});
    const current = requests.slice(5);
    finish(current.filter(request=>!request.path.includes('/registry/')),2);
    await vi.advanceTimersByTimeAsync(0);
    expect(finished).toBe(false);
    expect(store.getSnapshot().scene?.placements[0].revision).toBe(2);
    expect(store.getSnapshot().status.placement.loading).toBe(false);
    expect(store.getSnapshot().status.workflow.loading).toBe(false);
    expect(store.getSnapshot().status.registry.loading).toBe(true);
    await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS);
    await refresh;
    expect(finished).toBe(true);
    const registry = current.find(request=>request.path.includes('/registry/'))!;
    expect(registry.signal.aborted).toBe(true);
    expect(store.getSnapshot().status.registry).toEqual({fetchedAt:previousRegistry,error:'Module registry unavailable',loading:false});
    const accepted = store.getSnapshot();
    registry.resolve(Response.json({items:[{id:'late-module'}]}));
    await vi.advanceTimersByTimeAsync(0);
    expect(store.getSnapshot()).toBe(accepted);
  });
});

function change(id:string,state:string):Change {
  return {id,state,site:'site-1',proposer:'Alex',approver:'',error:'',revision:1,created_at:'2026-09-30T12:00:00Z',
    payload:{asset_id:id,rack_id:'rack-1',u:1,face:'front',expected_revision:1,authority_epoch:1}};
}
function finishHistory(requests:PendingRequest[],items:Change[],nextCursor:string|null) {
  finish(requests.filter(request=>!request.path.includes('/workflow/')),1);
  requests.find(request=>request.path.includes('/workflow/'))!.resolve(Response.json({
    items,active_count:items.filter(item=>item.state!=='completed').length,
    history:{limit:50,next_cursor:nextCursor,has_more:nextCursor!==null},
  }));
}

describe('completed change history',()=>{
  it('keeps unfinished changes visible and polls the selected history page until navigation',async()=>{
    const requests = controlledNetwork();
    const store = createOperationsData('operator');
    const firstPage = store.refresh();
    finishHistory(requests,[change('active','awaiting_approval'),change('recent','completed')],'older+/=');
    await firstPage;
    expect(store.getSnapshot().changeHistory).toEqual({page:1,nextCursor:'older+/=',hasMore:true});
    const older = store.olderChanges();
    expect(requests[7].path).toBe('/api/workflow/changes?history_cursor=older%2B%2F%3D');
    // Retain the current queue while the new page is loading.
    expect(store.getSnapshot().changes.map(item=>item.id)).toEqual(['active','recent']);
    finishHistory(requests.slice(5),[change('active','approved'),change('new-active','awaiting_approval'),change('old','completed')],null);
    await older;
    expect(store.getSnapshot().changes.map(item=>item.id)).toEqual(['active','new-active','old']);
    expect(store.getSnapshot().changeHistory).toEqual({page:2,nextCursor:null,hasMore:false});
    const poll = store.refresh();
    expect(requests[12].path).toBe('/api/workflow/changes?history_cursor=older%2B%2F%3D');
    finishHistory(requests.slice(10),[change('active','executing'),change('new-active','approved'),change('old','completed')],null);
    await poll;
    expect(store.getSnapshot().changeHistory.page).toBe(2);
    expect(store.getSnapshot().changes[0].state).toBe('executing');
    const newer = store.newerChanges();
    expect(requests[17].path).toBe('/api/workflow/changes');
    finishHistory(requests.slice(15),[change('active','executing'),change('new-active','approved'),change('recent','completed')],'older+/=');
    await newer;
    expect(store.getSnapshot().changeHistory.page).toBe(1);
    expect(store.getSnapshot().changes.map(item=>item.id)).toEqual(['active','new-active','recent']);
  });

  it('retains the displayed page after a failed page request and retries the same cursor',async()=>{
    const requests = controlledNetwork();
    const store = createOperationsData('operator');
    const firstPage = store.refresh();
    finishHistory(requests,[change('active','approved'),change('recent','completed')],'older');
    await firstPage;
    const older = store.olderChanges();
    finish(requests.slice(5),2,['workflow']);
    await older;
    expect(store.getSnapshot().changeHistory.page).toBe(1);
    expect(store.getSnapshot().changes.map(item=>item.id)).toEqual(['active','recent']);
    expect(store.getSnapshot().status.workflow.error).toBe('Workflow unavailable');
    const retry = store.olderChanges();
    expect(requests[12].path).toBe('/api/workflow/changes?history_cursor=older');
    finishHistory(requests.slice(10),[change('active','approved'),change('old','completed')],null);
    await retry;
    expect(store.getSnapshot().changeHistory.page).toBe(2);
  });
});
