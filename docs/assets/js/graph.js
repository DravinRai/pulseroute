/**
 * Venue graph model and constraint-aware shortest-path search.
 *
 * Browser counterpart of `src/pulseroute/graph.py`. Both implementations read
 * the SAME `data/stadium_graph.json` — the venue is defined exactly once, so
 * there is no venue data to keep in sync.
 *
 * This module contains no DOM code and no AI code: it is pure, deterministic
 * routing that can be unit-tested in isolation.
 */

/** Vertical-transition modes that require stepping / are not wheelchair-usable. */
export const STEP_MODES = new Set(["stair", "escalator"]);

// Objective weights — mirror of the constants in graph.py.
const CO2_WEIGHT_GREEN = 10.0;
const TIME_TIEBREAK_GREEN = 0.01;
const CO2_WEIGHT_BALANCED = 2.0;

export class NoRouteError extends Error {}

/**
 * Binary min-heap keyed on element[0].
 *
 * Matches Python's `heapq`: O(log n) push/pop. A naive array that re-sorts on
 * every pop would make the search O(V^2 log V).
 */
class MinHeap {
  #items = [];

  get size() {
    return this.#items.length;
  }

  push(item) {
    const a = this.#items;
    a.push(item);
    let i = a.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (a[parent][0] <= a[i][0]) break;
      [a[parent], a[i]] = [a[i], a[parent]];
      i = parent;
    }
  }

  pop() {
    const a = this.#items;
    const top = a[0];
    const last = a.pop();
    if (a.length) {
      a[0] = last;
      let i = 0;
      for (;;) {
        const left = 2 * i + 1;
        const right = left + 1;
        let smallest = i;
        if (left < a.length && a[left][0] < a[smallest][0]) smallest = left;
        if (right < a.length && a[right][0] < a[smallest][0]) smallest = right;
        if (smallest === i) break;
        [a[smallest], a[i]] = [a[i], a[smallest]];
        i = smallest;
      }
    }
    return top;
  }
}

export class Graph {
  /**
   * @param {object} raw parsed contents of stadium_graph.json
   */
  constructor(raw) {
    this.nodes = new Map(
      raw.nodes.map((n) => [n.id, { id: n.id, label: n.label, level: n.level, type: n.type }]),
    );
    this.externalArrival = raw.external_arrival ?? {};

    /** @type {Map<string, Array<{to: string, edge: object}>>} */
    this.adjacency = new Map([...this.nodes.keys()].map((id) => [id, []]));
    this.edges = raw.edges.map((e) => {
      const edge = {
        frm: e.from,
        to: e.to,
        mode: e.mode,
        accessible: Boolean(e.accessible),
        distance: Number(e.distance),
        co2: Number(e.co2),
        baseTime: Number(e.base_time),
        congestionZone: e.congestion_zone ?? null,
        // Derived once at load (mirrors Edge.step_free): keeps a Set lookup out
        // of the inner search loop.
        stepFree: Boolean(e.accessible) && !STEP_MODES.has(e.mode),
      };
      // Undirected: both endpoints reference the SAME edge object.
      this.adjacency.get(edge.frm).push({ to: edge.to, edge });
      this.adjacency.get(edge.to).push({ to: edge.frm, edge });
      return edge;
    });
  }

  /** Fetch the shared venue definition and build the graph. */
  static async load(url = "data/stadium_graph.json") {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Could not load venue graph (HTTP ${response.status}).`);
    }
    return new Graph(await response.json());
  }

  label(nodeId) {
    return this.nodes.get(nodeId)?.label ?? nodeId;
  }

  /**
   * Build the per-edge cost function once, outside the search loop.
   * Returns `[searchCost, realTime, congestionApplied]` — carrying the real
   * traversal time alongside the search cost means reconstruction reuses it
   * rather than recomputing the congestion maths.
   */
  #makeCostFn(request, congestion) {
    const { optimize = "time", avoidCongestion = true } = request;
    return (edge) => {
      let time = edge.baseTime;
      let applied = false;
      const zone = edge.congestionZone;
      if (avoidCongestion && zone) {
        const factor = congestion[zone] ?? 0;
        if (factor) {
          time *= 1 + factor; // congestion inflates traversal time
          applied = true;
        }
      }
      let searchCost;
      if (optimize === "co2") {
        searchCost = edge.co2 * CO2_WEIGHT_GREEN + time * TIME_TIEBREAK_GREEN;
      } else if (optimize === "balanced") {
        searchCost = time + edge.co2 * CO2_WEIGHT_BALANCED;
      } else {
        searchCost = time;
      }
      return [searchCost, time, applied];
    };
  }

  /**
   * Constraint-aware Dijkstra. O((V + E) log V).
   *
   * Hard constraints prune edges *during relaxation*, so an edge the user
   * cannot physically use never reaches the frontier and can never appear in
   * the result. This is what makes step-free routing a structural guarantee.
   */
  findRoute(request, congestion = {}) {
    const { origin, destination } = request;
    if (!this.nodes.has(origin)) throw new Error(`Unknown origin node: ${origin}`);
    if (!this.nodes.has(destination)) throw new Error(`Unknown destination node: ${destination}`);

    const stepFreeOnly = Boolean(request.step_free ?? request.stepFree);
    const cost = this.#makeCostFn(request, congestion);

    const dist = new Map([[origin, 0]]);
    const prev = new Map();
    const visited = new Set();
    const frontier = new MinHeap();
    frontier.push([0, origin]);
    let congestionApplied = false;

    while (frontier.size) {
      const [d, u] = frontier.pop();
      if (visited.has(u)) continue; // stale heap entry (lazy deletion)
      visited.add(u);
      if (u === destination) break;

      for (const { to: v, edge } of this.adjacency.get(u)) {
        if (stepFreeOnly && !edge.stepFree) continue; // HARD accessibility constraint
        const [searchCost, realTime, applied] = cost(edge);
        if (applied) congestionApplied = true;
        const next = d + searchCost;
        if (next < (dist.get(v) ?? Infinity)) {
          dist.set(v, next);
          prev.set(v, { from: u, edge, realTime });
          frontier.push([next, v]);
        }
      }
    }

    if (!dist.has(destination)) {
      const reason = stepFreeOnly
        ? "no step-free path exists under current constraints"
        : "no path exists";
      throw new NoRouteError(`Cannot route ${origin} → ${destination}: ${reason}.`);
    }
    return this.#buildResult(request, prev, stepFreeOnly, congestionApplied);
  }

  #buildResult(request, prev, stepFree, congestionApplied) {
    const steps = [];
    let cur = request.destination;
    while (cur !== request.origin) {
      const { from, edge, realTime } = prev.get(cur);
      steps.push({
        frm: from,
        to: cur,
        mode: edge.mode,
        label: this.label(cur),
        distance: edge.distance,
        time: realTime,
        co2: edge.co2,
      });
      cur = from;
    }
    steps.reverse();

    const sum = (key) => steps.reduce((total, s) => total + s[key], 0);
    return {
      steps,
      totalDistance: sum("distance"),
      totalTime: sum("time"),
      totalCo2: sum("co2"),
      stepFree,
      optimize: request.optimize ?? "time",
      congestionApplied,
      nodeIds: [request.origin, ...steps.map((s) => s.to)],
    };
  }
}
