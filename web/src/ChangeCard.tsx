import type {Change} from './types';

type ChangeCardProps = {
  change:Change;
  assetName:string;
  rackLabel:string;
  role:string;
  demo?:boolean;
  busy:boolean;
  onApprove:()=>void;
  onExecute:()=>void;
  onReplan:()=>void;
};

export default function ChangeCard({change,assetName,rackLabel,role,demo=false,busy,onApprove,onExecute,onReplan}:ChangeCardProps) {
  return <article className="change-card">
    <div><strong>{assetName}</strong><span className={`state-badge ${change.state}`}>{change.state.replaceAll('_',' ')}</span></div>
    <p>Move to {rackLabel} · U{change.payload.u} · {change.payload.face}</p>
    <small>Proposed by {change.proposer}{change.approver?` · Approved by ${change.approver}`:''}</small>
    {change.error&&<p className="inline-error">{change.error}</p>}
    {change.state==='awaiting_nlyte'&&<p className="drawer-note">Staged only. Nlyte connectivity and write support must be verified.</p>}
    {change.state==='replan_required'&&<p className="drawer-note">Review current placement and submit a new proposal for separate approval.</p>}
    <div className="card-actions">
      {change.state==='replan_required'&&<button className="button primary" disabled={busy||!['operator','admin'].includes(role)} onClick={onReplan}>Re-plan move</button>}
      {change.state==='awaiting_approval'&&<button className="button secondary" disabled={busy||!['approver','admin'].includes(role)} onClick={onApprove}>{demo?`Approve as ${role==='approver'?'Jordan':'Admin'}`:'Approve change'}</button>}
      {['approved','executing'].includes(change.state)&&<button className="button primary" disabled={busy||!['operator','approver','admin'].includes(role)} onClick={onExecute}>{change.state==='executing'?'Resume execution':'Execute approved move'}</button>}
    </div>
  </article>;
}
