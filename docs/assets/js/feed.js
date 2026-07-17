/**
 * Deterministic congestion feed simulator.
 *
 * Browser counterpart of `src/pulseroute/feed.py`. In production this layer is
 * replaced by real telemetry (gate scan rates, Wi-Fi association counts, CV
 * people-counting); consumers only depend on the abstract shape it returns:
 * `{ zone: congestionFactor }`.
 */

export const ZONES = ["ne", "se", "sw", "nw"];

/**
 * Scripted matchday timeline (kickoff at 0', halftime ~45', full-time ~100').
 * Values are congestion multipliers: 0 = free-flowing, 1.0 doubles traversal time.
 * Kept sorted by minute so lookup is a binary search rather than a re-sort.
 */
const TIMELINE = [
  { minute: 0, factors: { ne: 0.9, se: 0.3, sw: 0.2, nw: 0.7 },
    note: "Pre-kickoff arrival surge at north/east gates." },
  { minute: 45, factors: { ne: 0.4, se: 1.6, sw: 1.4, nw: 0.5 },
    note: "Halftime: concession rush jams south concourse." },
  { minute: 100, factors: { ne: 1.8, se: 1.2, sw: 1.1, nw: 1.7 },
    note: "Full-time egress: heavy load on all exits." },
];

/** Index of the last entry whose minute is <= `minute` (binary search). */
function indexAtOrBefore(entries, minute) {
  let lo = 0;
  let hi = entries.length - 1;
  let found = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (entries[mid].minute <= minute) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found;
}

export class FeedSimulator {
  constructor(timeline = TIMELINE) {
    if (!timeline.length) throw new Error("FeedSimulator requires a non-empty timeline.");
    this.timeline = [...timeline].sort((a, b) => a.minute - b.minute);
  }

  /** The most recent scripted snapshot at or before `minute`. */
  snapshot(minute) {
    const entry = this.timeline[indexAtOrBefore(this.timeline, minute)];
    return { minute, factors: { ...entry.factors }, note: entry.note };
  }
}
