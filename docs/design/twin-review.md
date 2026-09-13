# Twin design review — foundation

The reference is the agreed Nlyte mental model, not an inspected customer screen.
All imagery and records in this foundation are synthetic. Exact Nlyte fidelity
requires customer walkthroughs. Review completed before frontend implementation.

## 1. Room floor plan / inspect

```
UNUM / OPERATIONS       Ashburn / Building 01 / Hall A      Search   Theme
------------------------------------------------------------------------
LOCATION TREE      | Hall A                 2D / 3D / Elevation | INSPECTOR
Ashburn           | 24 racks · data freshness               | Asset
  Hall A          | [A01][A02][A03][A04]                    | Identity
  Hall B          |           cold aisle                    | Placement
Dallas            | [B01][B02][B03][B04]                    | Ownership
Assets / filter   | heat / capacity / power / network       | Connections
                  | legend and observation time             | Propose move
------------------------------------------------------------------------
CHANGE QUEUE      | Pending approval · Awaiting Nlyte · Conflicts
```

Decision: floor plan is default. Rack labels, status symbols, power use and U
occupancy remain legible at reduced graphics. Inspector and selection survive
view switching. Use navy ink, warm gray canvas, teal selection, restrained amber
pending states and red conflict states. Compact enterprise density with generous
canvas space. Icons supplement labels, never replace them.

## 2. Elevation / proposed move

Front/rear toggle above an elevation with numbered U positions. Selected asset
has a solid outline; proposed destination uses a dashed ghost labeled PROPOSED.
Numeric rack/U controls are the keyboard equivalent of dragging an asset. The
preview shows validation before submitting. Submitting creates a change request;
the existing placement remains solid. A separate operator approves the request.
Execution revalidates reservations and authority. Nlyte-owned moves wait for
Nlyte; the demo must never imply a remote write succeeded.

## 3. Trace / heat

On-demand overlays show route lines, arrow direction, units, source and timestamp.
Synthetic temperatures explicitly say DEMO MEASUREMENT. Topology traces say
ILLUSTRATIVE TOPOLOGY, NOT LIVE FLOW. Unknown data is gray and labeled, not zero.
Power/network overlays have independent capability checks. An unavailable overlay
does not prevent asset inspection. Reduced motion disables path animation.

## 4. Queue / conflicts

Queue cards include proposer, source, state, target and reason. A conflict shows
baseline, owner, both candidate values, observation time and an authorized
resolution action. Resolution stages a reviewed value; it does not claim peer
convergence. Offline/stale states persist visibly in the main toolbar/inspector.

## Review outcomes

- Operational actions use API commands rather than scene mutation.
- Keyboard inputs cover selection, view switching and placement.
- Rendering and domain state are independent; one scene DTO feeds all views.
- Core UI remains useful if WebGL or optional overlays fail.
- Production usability acceptance by Nlyte operators remains an external gate.

## Home page and multiple cabinets — 2026-09-13 amendment

The default home page is a location directory. Choosing a location (or a named
hall on its card) opens its 2D floor plan. The sidebar contains only halls in the
current location, with All locations returning to the directory. Synthetic
Ashburn and Dallas records exercise separate site scopes.

Cabinet selection supports ordinary click, Ctrl/Cmd-click toggling, Shift-click
range selection, a persistent Multi-select mode, Select all and Clear. Selected
cabinets receive an outline and check marker plus accessible pressed state.
The inspector summarizes selected cabinets and the equipment table combines their
assets. Selection is local UI state and never implies a bulk physical move.
Changing hall/location resets the selection to the first cabinet in that hall.
