"""Operational-intelligence layer for venue staff / control room.

Turns the same live graph + congestion state into an aggregate decision brief.
The numeric risk assessment is deterministic; the LLM (when present) only phrases
the recommendation. Staff never receive an action the data didn't justify.
"""
from __future__ import annotations

from dataclasses import dataclass

from .feed import CongestionSnapshot

_ZONE_LABELS = {
    "ne": "North-East (Gate A/B ↔ concourse)",
    "se": "South-East (Gate B/C ↔ concourse)",
    "sw": "South-West (Gate C/D ↔ concourse)",
    "nw": "North-West (Gate D/A ↔ concourse)",
}
_ACTIONS = {
    "ne": "Open Gate A overflow lanes; steward reroute via West Concourse.",
    "se": "Add halftime concession stewards; signpost North restrooms.",
    "sw": "Protect step-free path to Section 114; hold South elevator for accessibility.",
    "nw": "Stagger West exit; coordinate shuttle hub dispatch.",
}


@dataclass
class OpsBrief:
    minute: int
    note: str
    ranked_zones: list[tuple[str, float]]
    recommended_actions: list[str]

    def as_text(self) -> str:
        lines = [f"OPERATIONS BRIEF — matchday minute {self.minute}", f"Context: {self.note}"]
        if not self.ranked_zones:
            lines.append("All zones free-flowing. No action required.")
            return "\n".join(lines)
        lines.append("Top congestion risks:")
        for zone, factor in self.ranked_zones:
            lines.append(f"  • {_ZONE_LABELS.get(zone, zone)} — load index {factor:.1f}")
        lines.append("Recommended actions:")
        for a in self.recommended_actions:
            lines.append(f"  → {a}")
        return "\n".join(lines)


def build_brief(snapshot: CongestionSnapshot, top_n: int = 3,
                threshold: float = 0.8) -> OpsBrief:
    ranked = sorted(snapshot.factors.items(), key=lambda kv: kv[1], reverse=True)
    ranked = [(z, f) for z, f in ranked if f >= threshold][:top_n]
    actions = [_ACTIONS[z] for z, _ in ranked if z in _ACTIONS]
    return OpsBrief(
        minute=snapshot.minute, note=snapshot.note,
        ranked_zones=ranked, recommended_actions=actions,
    )
