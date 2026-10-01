import {createDemoSession} from './authSession';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {api} from './api';

afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();vi.restoreAllMocks()});

describe('bounded API requests',()=>{
  it('aborts and rejects a transport that never responds, even if it ignores abort',async()=>{
    vi.useFakeTimers();
    let signal!:AbortSignal;
    vi.stubGlobal('fetch',vi.fn((_path:string,options:RequestInit)=>{
      signal = options.signal!;
      return new Promise<Response>(()=>{});
    }));
    const request = api('registry','modules',createDemoSession('operator'),undefined,{timeoutMs:100});
    const rejected = expect(request).rejects.toThrow('Request timed out');
    await vi.advanceTimersByTimeAsync(100);
    await rejected;
    expect(signal.aborted).toBe(true);
  });

  it('keeps the deadline active while reading an accepted response body',async()=>{
    vi.useFakeTimers();
    let signal!:AbortSignal;
    vi.stubGlobal('fetch',vi.fn(async(_path:string,options:RequestInit)=>{
      signal = options.signal!;
      return new Response(new ReadableStream({start(controller){
        controller.enqueue(new TextEncoder().encode('{"id":'));
      }}),{status:201});
    }));
    const request = api('workflow','changes',createDemoSession('operator'),{}, {timeoutMs:100});
    const rejected = expect(request).rejects.toThrow('Request timed out');
    await vi.advanceTimersByTimeAsync(100);
    await rejected;
    expect(signal.aborted).toBe(true);
  });

  it('cancels superseded requests promptly without waiting for their deadline',async()=>{
    const controller = new AbortController();
    let transportSignal!:AbortSignal;
    vi.stubGlobal('fetch',vi.fn((_path:string,options:RequestInit)=>{
      transportSignal = options.signal!;
      return new Promise<Response>(()=>{});
    }));
    const request = api('placement','scene',createDemoSession('operator'),undefined,{signal:controller.signal});
    const rejected = expect(request).rejects.toMatchObject({name:'AbortError'});
    controller.abort();
    await rejected;
    expect(transportSignal.aborted).toBe(true);
  });
});
