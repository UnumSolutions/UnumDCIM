import {afterEach, describe, expect, it, vi} from 'vitest';
import {ApiError} from './api';
import {createMoveSubmission, type MoveCommand} from './moveSubmission';

const command:MoveCommand = {asset_id:'asset-1',rack_id:'rack-2',u:10,face:'front',site:'site-1',expected_revision:1,authority_epoch:2};
type WireCommand = MoveCommand & {idempotency_key:string};
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks()});

describe('move proposal requests',()=>{
  it('retries an accepted proposal with the same key and payload after its response is lost',async()=>{
    const proposals = new Map<string, {id:string;payload:WireCommand}>();
    const preview = vi.fn();
    const submitted:WireCommand[] = [];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
      const payload = JSON.parse(options.body as string) as WireCommand;
      if(path==='/api/placement/preview') {
        preview();
        return Response.json({valid:true});
      }
      submitted.push(payload);
      const existing = proposals.get(payload.idempotency_key);
      if(existing) return Response.json(existing);
      proposals.set(payload.idempotency_key,{id:'change-1',payload});
      // The server has committed, but no acknowledgement reaches the client.
      throw new TypeError('Failed to fetch');
    }));
    const submission = createMoveSubmission('operator');
    await expect(submission.submit(command)).rejects.toThrow('Failed to fetch');
    // A background refresh changed both preconditions while the response was lost.
    const recovered = await submission.submit({...command,expected_revision:2,authority_epoch:3});
    expect(recovered.id).toBe('change-1');
    expect(proposals.size).toBe(1);
    expect(submitted).toHaveLength(2);
    expect(submitted[1]).toEqual(submitted[0]);
    expect(submitted[1].expected_revision).toBe(1);
    expect(preview).toHaveBeenCalledTimes(1);
  });

  it.each([401,408,429])('retains an ambiguous command through an HTTP %s retry failure',async(status)=>{
    const submitted:WireCommand[] = [];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
      if(path.includes('/preview')) return Response.json({valid:true});
      submitted.push(JSON.parse(options.body as string));
      if(submitted.length===1) throw new TypeError('Response lost after acceptance');
      if(submitted.length===2) return Response.json({error:'Retry later'},{status});
      return Response.json({id:'original-change'});
    }));
    const submission = createMoveSubmission('operator');
    await expect(submission.submit(command)).rejects.toThrow('Response lost');
    await expect(submission.submit(command)).rejects.toThrow('Retry later');
    await submission.submit({...command,expected_revision:3});
    expect(new Set(submitted.map(payload=>payload.idempotency_key)).size).toBe(1);
    expect(submitted[2]).toEqual(submitted[0]);
  });

  it('coalesces double submissions while the first network request is still pending',async()=>{
    let finishPreview!:(response:Response)=>void;
    const network = vi.fn((path:string)=>path.includes('/preview')
      ?new Promise<Response>(resolve=>{finishPreview=resolve})
      :Promise.resolve(Response.json({id:'change-1'})));
    vi.stubGlobal('fetch',network);
    const submission = createMoveSubmission('operator');
    const first = submission.submit(command);
    const second = submission.submit(command);
    expect(second).toBe(first);
    await expect(submission.submit({...command,u:20})).rejects.toThrow('already being submitted');
    finishPreview(Response.json({valid:true}));
    await first;
    expect(network).toHaveBeenCalledTimes(2);
  });

  it('uses fresh preconditions and a new key after an explicit server rejection',async()=>{
    const posted:WireCommand[] = [];
    let previewCount = 0;
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
      if(path.includes('/preview')) {
        previewCount++;
        return Response.json({valid:true});
      }
      posted.push(JSON.parse(options.body as string));
      return posted.length===1?Response.json({error:'Stale placement revision'},{status:409}):Response.json({id:'change-2'});
    }));
    const submission = createMoveSubmission('operator');
    await expect(submission.submit(command)).rejects.toBeInstanceOf(ApiError);
    await submission.submit({...command,expected_revision:2});
    expect(posted[1].idempotency_key).not.toBe(posted[0].idempotency_key);
    expect(posted[1].expected_revision).toBe(2);
    expect(previewCount).toBe(2);
  });

  it('starts a new proposal for an edited destination or explicit re-plan',async()=>{
    const posted:WireCommand[] = [];
    vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
      if(path.includes('/preview')) return Response.json({valid:true});
      posted.push(JSON.parse(options.body as string));
      return Response.json({error:'Gateway unavailable'},{status:502});
    }));
    const submission = createMoveSubmission('operator');
    await expect(submission.submit(command)).rejects.toThrow('Gateway unavailable');
    await expect(submission.submit({...command,u:20})).rejects.toThrow('Gateway unavailable');
    submission.reset();
    await expect(submission.submit({...command,u:20,expected_revision:3})).rejects.toThrow('Gateway unavailable');
    expect(new Set(posted.map(payload=>payload.idempotency_key)).size).toBe(3);
    expect(posted[2].expected_revision).toBe(3);
  });
});
