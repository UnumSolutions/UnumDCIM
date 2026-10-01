import type {Asset, Ghost, Placement, Rack} from './types';

type Props = {
  racks: Rack[];
  selectedRackIds: string[];
  placements: Placement[];
  assets: Asset[];
  selectedAsset: string;
  onSelectAsset: (id: string) => void;
  face: 'front' | 'rear';
  ghost: Ghost | null;
  demo?:boolean;
};

export default function RackElevations({racks, selectedRackIds, placements, assets,
  selectedAsset, onSelectAsset, face, ghost,demo=false}: Props) {
  const selected = racks.filter(rack => selectedRackIds.includes(rack.id));
  if (!selected.length) return <div className="empty elevation-empty" role="status">
    Select one or more cabinets from the sidebar or floor plan to view their elevations.
  </div>;

  const unit = 12;
  const maxU = Math.max(...selected.map(rack => rack.height_u));
  const drawingHeight = maxU * unit + 58;
  return <section className="elevation-comparison" aria-label="Selected cabinet elevations">
    <div className="elevation-comparison-heading">
      <span>{selected.length} cabinet{selected.length === 1 ? '' : 's'} · {face} elevations</span>
      <small>Scroll sideways to compare · select equipment to inspect</small>
    </div>
    <div className="elevation-strip" tabIndex={0} aria-label="Scrollable cabinet elevations">
      {selected.map(rack => {
        const installed = placements.filter(p => p.rack_id === rack.id);
        const used = installed.reduce((sum, p) => sum + p.height_u, 0);
        const top = 24 + (maxU - rack.height_u) * unit;
        const ghostPlacement = ghost?.rack_id === rack.id
          ? placements.find(p => p.asset_id === ghost.asset_id) : undefined;
        return <article className="elevation-cabinet" key={rack.id} aria-label={`Cabinet ${rack.label}`}>
          <header><h3>{rack.label}</h3><span>{used} / {rack.height_u} U used</span></header>
          <svg viewBox={`0 0 280 ${drawingHeight}`} role="group"
            aria-label={`${rack.label} ${face} rack elevation`}>
            <rect x="38" y={top - 6} width="226" height={rack.height_u * unit + 12}
              rx="5" fill="var(--rack)" />
            {Array.from({length: rack.height_u}, (_, i) => {
              const y = top + (rack.height_u - i - 1) * unit;
              return <g key={i}>
                <text x="29" y={y + 9} textAnchor="end" className="u-label">{i + 1}</text>
                <rect x="48" y={y} width="206" height={unit} fill="none" stroke="#73878a" strokeWidth=".45" />
              </g>;
            })}
            {installed.map(p => {
              const asset = assets.find(a => a.id === p.asset_id);
              const y = top + (rack.height_u - p.u - p.height_u + 1) * unit;
              const active = selectedAsset === p.asset_id;
              const name = asset?.name || p.asset_id;
              return <g key={p.asset_id} tabIndex={0} role="button" aria-pressed={active}
                aria-label={`${rack.label}: ${name}, U${p.u} to U${p.u + p.height_u - 1}`}
                className="elevation-device" onClick={() => onSelectAsset(p.asset_id)}
                onKeyDown={e => {if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault(); onSelectAsset(p.asset_id);
                }}}>
                <title>{name} · {asset?.model} · U{p.u}–U{p.u + p.height_u - 1}</title>
                <rect x="48" y={y + 1} width="206" height={p.height_u * unit - 2}
                  rx="2" fill={active ? '#267f72' : '#4c6268'}
                  stroke={active ? '#74dbbf' : '#7e9195'} strokeWidth="1.5" />
                <text x="57" y={y + p.height_u * unit / 2 + 4} className="device-label">
                  {face === 'rear' ? '◉ ◉  ' : ''}{name.length > 23 ? name.slice(0, 22) + '…' : name}
                </text>
                <circle cx="246" cy={y + 7} r="2" fill="#7ce0b1" />
              </g>;
            })}
            {ghost && ghostPlacement && <g aria-label={`Proposed placement in ${rack.label} at U${ghost.u}`}>
              <rect x="45" y={top + (rack.height_u - ghost.u - ghostPlacement.height_u + 1) * unit}
                width="212" height={ghostPlacement.height_u * unit} className="ghost-outline" />
              <text x="57" y={top + (rack.height_u - ghost.u - ghostPlacement.height_u + 1) * unit + 10}
                className="proposed-label">PROPOSED · U{ghost.u}</text>
            </g>}
            <text x="150" y={drawingHeight - 8} textAnchor="middle" className="floor-note">
              {face.toUpperCase()} · {rack.height_u}U
            </text>
          </svg>
        </article>;
      })}
    </div>
    <p className="elevation-note">Full-depth assets occupy both faces{demo?' · synthetic equipment':''}</p>
  </section>;
}
