"""Deterministic congestion feed simulator.

In production this layer would be replaced by real telemetry (gate scan rates,
Wi-Fi association counts, CV people-counting). We ship a reproducible simulator
so the demo and tests are fully offline and deterministic. The rest of the system
consumes only the abstract interface: a dict of {zone: congestion_factor}.
"""
from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

ZONES = ("ne", "se", "sw", "nw")


@dataclass(frozen=True, slots=True)
class CongestionSnapshot:
    minute: int
    factors: dict[str, float]     # zone -> multiplier delta (0.0 = free-flowing)
    note: str

    def risk_zones(self, threshold: float = 0.8) -> list[str]:
        return sorted(
            (z for z, f in self.factors.items() if f >= threshold),
            key=lambda z: self.factors[z],
            reverse=True,
        )


# A scripted matchday timeline (kickoff at minute 0, halftime ~45, full-time ~100).
# Values are congestion multipliers: 0.0 free, 1.0 = doubles traversal time.
_TIMELINE = {
    0:   ({"ne": 0.9, "se": 0.3, "sw": 0.2, "nw": 0.7}, "Pre-kickoff arrival surge at north/east gates."),
    45:  ({"ne": 0.4, "se": 1.6, "sw": 1.4, "nw": 0.5}, "Halftime: concession rush jams south concourse."),
    100: ({"ne": 1.8, "se": 1.2, "sw": 1.1, "nw": 1.7}, "Full-time egress: heavy load on all exits."),
}


class FeedSimulator:
    """Serves the scripted snapshot in effect at a given matchday minute.

    The timeline keys are sorted **once** at construction, so each lookup is an
    ``O(log n)`` binary search rather than re-sorting the timeline per call.
    """

    def __init__(self, timeline: dict[int, tuple[dict[str, float], str]] | None = None):
        self._timeline = timeline or _TIMELINE
        self._keys = sorted(self._timeline)
        if not self._keys:
            raise ValueError("FeedSimulator requires a non-empty timeline.")

    def snapshot(self, minute: int) -> CongestionSnapshot:
        """Return the most recent scripted snapshot at or before `minute`."""
        idx = bisect_right(self._keys, minute) - 1
        key = self._keys[max(idx, 0)]
        factors, note = self._timeline[key]
        return CongestionSnapshot(minute=minute, factors=dict(factors), note=note)

    @classmethod
    def from_json(cls, path: str | Path) -> FeedSimulator:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        timeline = {int(k): (v["factors"], v["note"]) for k, v in raw.items()}
        return cls(timeline)
