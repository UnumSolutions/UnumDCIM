import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import ChangeCard from './ChangeCard';
import type {Change} from './types';

const change:Change = {
  id:'change-1',site:'site-1',proposer:'Alex',approver:'Jordan',state:'replan_required',
  error:'Reservation expired',revision:3,created_at:'2026-09-13T12:00:00Z',
  payload:{asset_id:'asset-1',rack_id:'rack-2',u:10,face:'front',expected_revision:1,authority_epoch:1},
};
function render(state:string,role='operator') {
  return renderToStaticMarkup(<ChangeCard change={{...change,state}} assetName="Server one"
    rackLabel="A02" role={role} busy={false} onApprove={()=>{}} onExecute={()=>{}} onReplan={()=>{}}/>);
}

describe('change recovery controls',()=>{
  it('offers a new approved plan for an expired reservation without retrying its terminal execution',()=>{
    const html = render('replan_required');
    expect(html).toContain('Re-plan move');
    expect(html).toContain('new proposal for separate approval');
    expect(html).not.toContain('Resume execution');
    expect(html).not.toContain('Execute approved move');
    expect(html).toContain('Reservation expired');
  });
  it('resumes an ambiguous execution and requires a proposer for a new plan',()=>{
    expect(render('executing')).toContain('Resume execution');
    expect(render('executing')).not.toContain('Re-plan move');
    expect(render('replan_required','approver')).toMatch(/disabled=""[^>]*>Re-plan move/);
    expect(render('completed')).not.toContain('Re-plan move');
  });
});
