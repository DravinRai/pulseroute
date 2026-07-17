/**
 * Operational-intelligence layer for venue staff / control room.
 *
 * Browser counterpart of `src/pulseroute/ops.py`. The numeric risk assessment
 * is deterministic; in production an LLM would only phrase the recommendation.
 * Staff never receive an action the data did not justify.
 */

export const ZONE_LABELS = {
  ne: "North-East · Gate A/B ↔ concourse",
  se: "South-East · Gate B/C ↔ concourse",
  sw: "South-West · Gate C/D ↔ concourse",
  nw: "North-West · Gate D/A ↔ concourse",
};

const ACTIONS = {
  ne: "Open Gate A overflow lanes; steward reroute via West Concourse.",
  se: "Add halftime concession stewards; signpost North restrooms.",
  sw: "Protect step-free path to Section 114; hold South elevator for accessibility.",
  nw: "Stagger West exit; coordinate shuttle hub dispatch.",
};

const DEFAULT_TOP_N = 3;
const DEFAULT_THRESHOLD = 0.8;

/**
 * Rank congested zones and pair each with its standing mitigation.
 * @returns {{minute: number, note: string, ranked: Array<[string, number]>, actions: string[]}}
 */
export function buildBrief(snapshot, topN = DEFAULT_TOP_N, threshold = DEFAULT_THRESHOLD) {
  const ranked = Object.entries(snapshot.factors)
    .sort((a, b) => b[1] - a[1])
    .filter(([, factor]) => factor >= threshold)
    .slice(0, topN);

  return {
    minute: snapshot.minute,
    note: snapshot.note,
    ranked,
    actions: ranked.map(([zone]) => ACTIONS[zone]).filter(Boolean),
  };
}
