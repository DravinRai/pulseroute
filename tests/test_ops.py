"""Tests for the operational-intelligence briefing layer."""
from pulseroute.feed import FeedSimulator
from pulseroute.ops import build_brief


def test_halftime_flags_south_zones():
    snap = FeedSimulator().snapshot(45)
    brief = build_brief(snap)
    zones = {z for z, _ in brief.ranked_zones}
    assert "se" in zones or "sw" in zones
    assert brief.recommended_actions


def test_quiet_period_low_risk():
    # A synthetic all-quiet timeline yields no flagged zones.
    quiet = FeedSimulator({0: ({"ne": 0.0, "se": 0.1, "sw": 0.0, "nw": 0.1}, "calm")})
    brief = build_brief(quiet.snapshot(0))
    assert brief.ranked_zones == []
    assert "No action" in brief.as_text()


def test_brief_ranks_by_severity():
    snap = FeedSimulator().snapshot(100)  # full-time egress, everything high
    brief = build_brief(snap, top_n=3)
    factors = [f for _, f in brief.ranked_zones]
    assert factors == sorted(factors, reverse=True)
    assert len(brief.ranked_zones) <= 3
