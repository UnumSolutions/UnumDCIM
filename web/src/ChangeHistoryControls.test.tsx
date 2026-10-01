import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe,expect,it} from 'vitest';
import ChangeHistoryControls from './ChangeHistoryControls';

function render(page:number,hasMore:boolean,loading=false) {
  return renderToStaticMarkup(<ChangeHistoryControls history={{page,hasMore,nextCursor:hasMore?'older':null}}
    loading={loading} onOlder={()=>{}} onNewer={()=>{}}/>);
}

describe('change history navigation',()=>{
  it('offers only available directions and identifies the completed-history page',()=>{
    expect(render(1,true)).toContain('Completed history · page 1');
    expect(render(1,true)).toMatch(/disabled=""[^>]*>Newer history/);
    expect(render(1,true)).not.toMatch(/disabled=""[^>]*>Older history/);
    expect(render(2,false)).not.toMatch(/disabled=""[^>]*>Newer history/);
    expect(render(2,false)).toMatch(/disabled=""[^>]*>Older history/);
  });
  it('disables navigation during a request and explains that unfinished changes remain available',()=>{
    const html = render(2,true,true);
    expect(html).toMatch(/disabled=""[^>]*>Newer history/);
    expect(html).toMatch(/disabled=""[^>]*>Older history/);
    expect(html).toContain('All unfinished changes remain visible on every page.');
  });
});
