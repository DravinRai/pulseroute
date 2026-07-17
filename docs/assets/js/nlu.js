/**
 * GenAI boundary layer — offline (rule-based) backend.
 *
 * Browser counterpart of the deterministic fallback in
 * `src/pulseroute/llm_agent.py`.
 *
 * STRICT BOUNDARY: this module turns free text INTO a structured request, and
 * turns a computed result INTO prose. It never decides a path — it cannot even
 * see the graph. The worst a bad parse can do is ask for an impossible route,
 * which the engine rejects; it can never fabricate a staircase into a
 * wheelchair user's directions.
 *
 * The deployed demo ships this offline parser so the site is static, free and
 * key-less. With an ANTHROPIC_API_KEY the Python package swaps in Claude for
 * genuine multilingual understanding — same contract, same types.
 */

/** Human-friendly aliases mapped to graph node ids. */
export const ALIASES = {
  "metro": "metro", "subway": "metro", "train": "metro", "line 2": "metro",
  "shuttle hub": "shuttle_hub", "shuttle": "shuttle_hub",
  "accessible parking": "parking_accessible", "parking": "parking_accessible",
  "blue lot": "parking_accessible", "car": "parking_accessible",
  "rideshare": "rideshare", "uber": "rideshare", "taxi": "rideshare", "drop-off": "rideshare",
  "gate a": "gate_A", "gate b": "gate_B", "gate c": "gate_C", "gate d": "gate_D",
  "north concourse": "conc_N", "east concourse": "conc_E",
  "south concourse": "conc_S", "west concourse": "conc_W",
  "section 101": "sec_101", "section 108": "sec_108",
  "section 114": "sec_114", "section 122": "sec_122",
  "sec 101": "sec_101", "sec 108": "sec_108", "sec 114": "sec_114", "sec 122": "sec_122",
  "accessible restroom": "restroom_acc_S", "accessible bathroom": "restroom_acc_S",
  "restroom": "restroom_N", "bathroom": "restroom_N", "toilet": "restroom_N",
  "sensory room": "sensory_room", "calm room": "sensory_room", "quiet room": "sensory_room",
  "first aid": "first_aid_E", "medical": "first_aid_E",
  "concession": "concession_W", "food": "concession_W",
};

/**
 * Sorted ONCE at module load, longest-first, so "accessible restroom" always
 * beats the substring "restroom". Sorting per parse would repeat this work on
 * every keystroke-driven request.
 */
const ALIAS_KEYS_LONGEST_FIRST = Object.keys(ALIASES).sort((a, b) => b.length - a.length);

const STEP_FREE_HINTS = [
  "wheelchair", "step-free", "step free", "no stairs", "accessible route",
  "cannot climb", "can't climb", "mobility", "walker", "stroller", "avoid stairs",
];
const CO2_HINTS = ["greenest", "lowest carbon", "eco", "sustainable", "least co2", "climate"];

const FROM_TO = /\bfrom\b(.*?)\bto\b(.*)/s;

const MODE_VERBS = {
  walk: "Walk", walk_outdoor: "Walk", stair: "Take the stairs",
  elevator: "Take the elevator", escalator: "Take the escalator",
  ramp: "Take the ramp", transit_shuttle: "Board the accessible shuttle",
  transit_metro: "Take the metro",
};

export const modeVerb = (mode) => MODE_VERBS[mode] ?? "Proceed";

function matchAlias(text) {
  const lowered = text.toLowerCase();
  for (const alias of ALIAS_KEYS_LONGEST_FIRST) {
    if (lowered.includes(alias)) return ALIASES[alias];
  }
  return null;
}

/** Distinct node ids, ordered by where they appear in the text. */
function aliasesInReadingOrder(lowered) {
  const hits = [];
  for (const alias of ALIAS_KEYS_LONGEST_FIRST) {
    const idx = lowered.indexOf(alias);
    if (idx !== -1) hits.push([idx, ALIASES[alias]]);
  }
  hits.sort((a, b) => a[0] - b[0]);
  const ordered = [];
  for (const [, nodeId] of hits) {
    if (!ordered.includes(nodeId)) ordered.push(nodeId);
  }
  return ordered;
}

/**
 * Parse free text into a structured RouteRequest.
 * @throws {Error} when an origin and destination cannot both be identified.
 */
export function parseRequest(text) {
  const lowered = text.toLowerCase();
  let origin = null;
  let destination = null;

  const match = lowered.match(FROM_TO);
  if (match) {
    origin = matchAlias(match[1]);
    destination = matchAlias(match[2]);
  }
  if (!origin || !destination) {
    const ordered = aliasesInReadingOrder(lowered);
    origin ??= ordered[0] ?? null;
    destination ??= ordered[1] ?? null;
  }
  if (!origin || !destination) {
    throw new Error("Could not identify both an origin and a destination. Try “from X to Y”.");
  }

  return {
    origin,
    destination,
    step_free: STEP_FREE_HINTS.some((h) => lowered.includes(h)),
    optimize: CO2_HINTS.some((h) => lowered.includes(h)) ? "co2" : "time",
    avoidCongestion: true,
  };
}
