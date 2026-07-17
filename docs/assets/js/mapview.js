/**
 * Schematic stadium map rendering.
 *
 * Presentation only — this module never computes a route, it just draws one it
 * is handed.
 *
 * NOTE ON COORDINATES: the layout below is *schematic*, chosen for legibility
 * and collision-free labels, NOT drawn to scale. This is exactly why the engine
 * uses Dijkstra rather than A*: a straight-line heuristic over these positions
 * would not be admissible against the venue's real distances, and an
 * inadmissible heuristic can silently return a worse step-free detour.
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const VIEWBOX = { width: 1000, height: 720 };
const CENTER = { x: 500, y: 350 };

/** Node category -> CSS custom property used for its dot colour. */
const CATEGORY_COLOUR = {
  transit: "var(--n-transit)", parking: "var(--n-transit)", gate: "var(--n-gate)",
  concourse: "var(--n-conc)", seating: "var(--n-seat)", restroom: "var(--n-rest)",
  restroom_accessible: "var(--n-rest)", sensory: "var(--n-sensory)",
  first_aid: "var(--n-aid)", concession: "var(--n-food)",
};

/**
 * Hand-placed layout: { x, y, anchor, dx, dy, short }.
 * `anchor`/`dx`/`dy` position each label so that no two labels overlap — this is
 * asserted by a rendering check rather than left to chance.
 */
export const LAYOUT = {
  metro: { x: 250, y: 150, anchor: "middle", dx: 0, dy: -16, short: "Metro" },
  gate_A: { x: 500, y: 150, anchor: "middle", dx: 0, dy: -16, short: "Gate A" },
  gate_B: { x: 812, y: 350, anchor: "start", dx: 16, dy: 5, short: "Gate B" },
  gate_C: { x: 500, y: 566, anchor: "middle", dx: 0, dy: 30, short: "Gate C" },
  gate_D: { x: 188, y: 350, anchor: "end", dx: -16, dy: 5, short: "Gate D" },
  shuttle_hub: { x: 500, y: 668, anchor: "middle", dx: 0, dy: 30, short: "Shuttle Hub" },
  parking_accessible: { x: 770, y: 600, anchor: "start", dx: 16, dy: 5, short: "Accessible Parking" },
  rideshare: { x: 172, y: 548, anchor: "end", dx: -16, dy: 5, short: "Rideshare" },
  conc_N: { x: 500, y: 252, anchor: "end", dx: -14, dy: -8, short: "N. Concourse" },
  conc_E: { x: 688, y: 350, anchor: "start", dx: 16, dy: -8, short: "E. Concourse" },
  conc_S: { x: 500, y: 448, anchor: "end", dx: -14, dy: 20, short: "S. Concourse" },
  conc_W: { x: 312, y: 350, anchor: "end", dx: -16, dy: -8, short: "W. Concourse" },
  sec_101: { x: 520, y: 308, anchor: "start", dx: 13, dy: 4, short: "Sec 101" },
  sec_108: { x: 606, y: 362, anchor: "start", dx: 13, dy: 15, short: "Sec 108" },
  sec_114: { x: 500, y: 396, anchor: "start", dx: 13, dy: 4, short: "Sec 114" },
  sec_122: { x: 398, y: 350, anchor: "middle", dx: 0, dy: 22, short: "Sec 122" },
  restroom_N: { x: 428, y: 218, anchor: "end", dx: -12, dy: 4, short: "Restroom" },
  restroom_acc_S: { x: 592, y: 472, anchor: "start", dx: 12, dy: 4, short: "Accessible WC" },
  sensory_room: { x: 470, y: 502, anchor: "middle", dx: 0, dy: 20, short: "Sensory Room" },
  first_aid_E: { x: 732, y: 420, anchor: "start", dx: 13, dy: 4, short: "First Aid" },
  concession_W: { x: 262, y: 286, anchor: "end", dx: -12, dy: -2, short: "Concession" },
};

const TRANSIT_CURVE_OFFSET = 70;
const CONGESTION_HOT_THRESHOLD = 1;

function el(name, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

const DEFS = `
  <linearGradient id="routeGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#4f46e5"/><stop offset="0.55" stop-color="#7c3aed"/>
    <stop offset="1" stop-color="#06b6d4"/>
  </linearGradient>
  <radialGradient id="pitchGrad" cx="0.5" cy="0.4" r="0.7">
    <stop offset="0" stop-color="#1f9d57"/><stop offset="1" stop-color="#14713e"/>
  </radialGradient>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="4" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>`;

function drawStadiumShell(svg) {
  svg.appendChild(el("ellipse", {
    cx: CENTER.x, cy: CENTER.y, rx: 224, ry: 150, fill: "none",
    stroke: "color-mix(in srgb,var(--n-conc) 30%,transparent)",
    "stroke-width": 58, opacity: 0.16,
  }));
  svg.appendChild(el("ellipse", {
    cx: CENTER.x, cy: CENTER.y, rx: 150, ry: 96, fill: "url(#pitchGrad)", opacity: 0.9,
  }));
  svg.appendChild(el("line", {
    x1: CENTER.x, y1: 254, x2: CENTER.x, y2: 446,
    stroke: "rgba(255,255,255,.55)", "stroke-width": 2,
  }));
  svg.appendChild(el("circle", {
    cx: CENTER.x, cy: CENTER.y, r: 30, fill: "none",
    stroke: "rgba(255,255,255,.55)", "stroke-width": 2,
  }));
  svg.appendChild(el("text", {
    x: CENTER.x, y: CENTER.y + 5, "text-anchor": "middle",
    fill: "rgba(255,255,255,.8)", "font-size": 13, "font-weight": 800, "letter-spacing": "2px",
  }, "PITCH"));
}

function drawEdges(svg, graph, congestion) {
  const drawn = new Set();
  for (const edge of graph.edges) {
    const key = [edge.frm, edge.to].sort().join("|");
    if (drawn.has(key)) continue;
    drawn.add(key);

    const a = LAYOUT[edge.frm];
    const b = LAYOUT[edge.to];
    const isTransit = edge.mode.startsWith("transit");
    const hot = edge.congestionZone &&
      (congestion?.[edge.congestionZone] ?? 0) >= CONGESTION_HOT_THRESHOLD;
    const cls = `edge${isTransit ? " transit" : ""}${hot ? " hot" : ""}`;

    if (isTransit) {
      // Bow transit legs outward so they arc around the pitch instead of
      // cutting across it.
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      const nx = -(b.y - a.y);
      const ny = b.x - a.x;
      const len = Math.hypot(nx, ny) || 1;
      const cx = mx + (nx / len) * TRANSIT_CURVE_OFFSET;
      const cy = my + (ny / len) * TRANSIT_CURVE_OFFSET;
      svg.appendChild(el("path", { class: cls, d: `M${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}` }));
    } else {
      svg.appendChild(el("line", { class: cls, x1: a.x, y1: a.y, x2: b.x, y2: b.y }));
    }
  }
}

function drawRoutePath(svg, nodeIds, animate) {
  const d = nodeIds
    .map((id, i) => `${i ? "L" : "M"}${LAYOUT[id].x} ${LAYOUT[id].y}`)
    .join(" ");
  const path = el("path", { class: "rpath", d });
  svg.appendChild(path);

  if (!animate) return;
  requestAnimationFrame(() => {
    try {
      const length = path.getTotalLength();
      path.style.strokeDasharray = length;
      path.style.strokeDashoffset = length;
      path.getBoundingClientRect(); // force reflow so the transition runs
      path.style.transition = "stroke-dashoffset .9s ease";
      path.style.strokeDashoffset = 0;
    } catch {
      /* getTotalLength is unavailable in some headless engines; skip animation */
    }
  });
}

function drawNodes(svg, graph, routeIds) {
  const onRoute = new Set(routeIds);
  const first = routeIds[0];
  const last = routeIds.at(-1);

  for (const node of graph.nodes.values()) {
    const pos = LAYOUT[node.id];
    if (!pos) continue;
    const active = onRoute.has(node.id);
    const group = el("g", { class: `node ${active ? "on" : "dim"}` });

    if (active) {
      const role = node.id === first ? "start" : node.id === last ? "end" : "mid";
      if (role === "start") {
        group.appendChild(el("circle", { class: "pulse-ring", cx: pos.x, cy: pos.y, r: 9 }));
      }
      group.appendChild(el("circle", {
        class: `rnode ${role}`, cx: pos.x, cy: pos.y, r: role === "mid" ? 6.5 : 8,
      }));
    } else {
      group.appendChild(el("circle", {
        class: "node-dot", cx: pos.x, cy: pos.y, r: 5.5,
        fill: CATEGORY_COLOUR[node.type] ?? "var(--n-conc)",
      }));
    }
    group.appendChild(el("text", {
      class: "node-lbl", x: pos.x + pos.dx, y: pos.y + pos.dy + 4, "text-anchor": pos.anchor,
    }, pos.short));
    // Accessible name for assistive tech reading the map.
    group.appendChild(el("title", {}, node.label));
    svg.appendChild(group);
  }
}

/**
 * Render the stadium map into `mount`.
 * @param {HTMLElement} mount
 * @param {Graph} graph
 * @param {object|null} result route to highlight, or null for an empty map
 * @param {object} congestion zone -> factor
 * @param {{animate?: boolean}} [options]
 */
export function drawMap(mount, graph, result, congestion, { animate = true } = {}) {
  const routeIds = result?.nodeIds ?? [];
  const svg = el("svg", {
    viewBox: `0 0 ${VIEWBOX.width} ${VIEWBOX.height}`,
    class: "map",
    role: "img",
    "aria-label": result
      ? `Stadium map with the computed route highlighted, from ${graph.label(routeIds[0])} to ${graph.label(routeIds.at(-1))}.`
      : "Schematic stadium map.",
  });
  svg.innerHTML = `<defs>${DEFS}</defs>`;

  drawStadiumShell(svg);
  drawEdges(svg, graph, congestion);
  if (routeIds.length > 1) drawRoutePath(svg, routeIds, animate);
  drawNodes(svg, graph, routeIds);

  mount.replaceChildren(svg);
}
