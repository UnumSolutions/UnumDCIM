import type {ChangeHistory} from './operationsData';

type Props = {
  history:ChangeHistory;
  loading:boolean;
  onOlder:()=>void;
  onNewer:()=>void;
};

export default function ChangeHistoryControls({history,loading,onOlder,onNewer}:Props) {
  return <nav className="change-history-controls" aria-label="Completed change history">
    <span>Completed history · page {history.page}</span>
    <div>
      <button className="button secondary" disabled={loading||history.page===1} onClick={onNewer}>Newer history</button>
      <button className="button secondary" disabled={loading||!history.hasMore} onClick={onOlder}>Older history</button>
    </div>
    <small>All unfinished changes remain visible on every page.</small>
  </nav>;
}
