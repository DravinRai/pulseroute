/** Inline SVG icon set. No external requests, no icon-font payload. */

const wrap = (paths, size = 14) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" ` +
  `stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;

const WALKER =
  '<circle cx="12" cy="4.2" r="2"/><path d="M12 6.5v6M12 9l-3 3M12 9l3 2.4M12 12.5l-2 6.5M12 12.5l2 6.5"/>';

/** Per-travel-mode glyphs, keyed by the graph's `mode` field. */
const MODE_PATHS = {
  walk: WALKER,
  walk_outdoor: WALKER,
  stair: '<path d="M3 18h4v-4h4v-4h4V6h4"/>',
  escalator: '<path d="M4 18 20 6M8 18H4v-2M20 6h-4"/>',
  ramp: '<path d="M4 18 20 8M4 18h16"/><circle cx="9" cy="13" r="1.6"/>',
  elevator: '<rect x="6" y="3" width="12" height="18" rx="1.5"/><path d="M12 7.5 10 11h4zM12 16.5 10 13h4z"/>',
  transit_shuttle:
    '<rect x="3" y="6" width="18" height="9" rx="2"/><path d="M3 11h18"/>' +
    '<circle cx="7.5" cy="18" r="1.6"/><circle cx="16.5" cy="18" r="1.6"/>',
  transit_metro:
    '<rect x="5" y="4" width="14" height="12" rx="3"/><path d="M5 11h14"/><path d="m7 20 2-3M17 20l-2-3"/>',
};

export const modeIcon = (mode, size = 16) =>
  wrap(MODE_PATHS[mode] ?? '<circle cx="12" cy="12" r="7"/>', size);

export const okIcon = () => wrap('<path d="M20 6 9 17l-5-5"/>');
export const warnIcon = () =>
  wrap('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>');
export const leafIcon = () =>
  wrap('<path d="M11 20A7 7 0 0 1 4 13c0-6 8-9 16-9 0 8-3 16-9 16z"/><path d="M4 20c3-4 6-6 10-7"/>');
export const clockIcon = () => wrap('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>');
export const rulerIcon = () =>
  wrap('<path d="M3 9 9 3l12 12-6 6z"/><path d="m7 9 1 1M10 6l1 1M13 9l1 1M9 13l1 1"/>');
export const stepIcon = () => wrap('<path d="M4 18h4v-4h4v-4h4V6h4"/>');
export const pinIcon = () =>
  wrap('<path d="M12 21s-7-6.3-7-11a7 7 0 0 1 14 0c0 4.7-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>', 15);
export const flagIcon = () => wrap('<path d="M4 22V4M4 4h13l-2 4 2 4H4"/>', 15);
export const sparkIcon = () =>
  wrap('<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>', 13);
