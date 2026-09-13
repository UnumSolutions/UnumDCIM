import {api, ApiError} from './api';
import type {Change, Ghost} from './types';

export type MoveCommand = Ghost & {
  site:string;
  expected_revision:number;
  authority_epoch:number;
};
type PendingMove = {
  identity:string;
  command:MoveCommand & {idempotency_key:string};
  sent:boolean;
  inFlight:Promise<Change>|null;
};

/** Preserve an ambiguous command verbatim, including revision, until acknowledged. */
export function createMoveSubmission(role:string) {
  let pending:PendingMove|null = null;
  return {
    reset:()=>{if(!pending?.inFlight) pending = null},
    submit(command:MoveCommand):Promise<Change> {
      const identity = JSON.stringify([
        command.asset_id,command.rack_id,command.u,command.face,command.site,
      ]);
      if(pending?.inFlight) {
        if(pending.identity===identity) return pending.inFlight;
        return Promise.reject(new Error('A move proposal is already being submitted.'));
      }
      if(!pending || pending.identity!==identity) {
        pending = {identity,command:{...command,idempotency_key:crypto.randomUUID()},sent:false,inFlight:null};
      }
      const attempt = pending;
      attempt.inFlight = (async()=>{
        try {
          // After an ambiguous POST, retry it directly. Previewing again could
          // fail because the accepted proposal has since moved the asset.
          if(!attempt.sent) {
            await api('placement','preview',role,attempt.command);
          }
          attempt.sent = true;
          const result = await api<Change>('workflow','changes',role,attempt.command);
          pending = null;
          return result;
        } catch(error) {
          // Invalid commands can use newly refreshed preconditions next time.
          // Authentication, throttling, and timeout responses may occur while
          // recovering an already accepted command, so retain its original key.
          if(error instanceof ApiError && [400,404,409,422].includes(error.status)) {
            pending = null;
          }
          throw error;
        } finally {
          attempt.inFlight = null;
        }
      })();
      return attempt.inFlight;
    },
  };
}
