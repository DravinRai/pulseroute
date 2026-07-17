"""Core routing + safety-invariant tests. Fully offline and deterministic."""
from dataclasses import FrozenInstanceError

import pytest

from pulseroute import VENUE_GRAPH_PATH
from pulseroute.graph import STEP_MODES, Graph, RouteRequest


@pytest.fixture(scope="module")
def graph():
    return Graph.from_json(VENUE_GRAPH_PATH)


def test_graph_loads(graph):
    assert "sec_114" in graph.nodes
    assert graph.nodes["sec_114"].type == "seating"
    assert len(graph.edges) > 20


def test_basic_route_exists(graph):
    req = RouteRequest(origin="metro", destination="sec_114")
    result = graph.find_route(req)
    assert result.node_ids[0] == "metro"
    assert result.node_ids[-1] == "sec_114"
    assert result.total_time > 0


# ---- THE safety-critical invariant --------------------------------------
def test_step_free_route_never_contains_stairs(graph):
    """A wheelchair user must NEVER be routed over a stair/escalator.
    This is guaranteed structurally by edge pruning, not by an LLM promise."""
    req = RouteRequest(origin="metro", destination="sec_114", step_free=True)
    result = graph.find_route(req)
    assert result.step_free
    for step in result.steps:
        assert step.mode not in STEP_MODES, f"step-free route used {step.mode}!"


def test_step_free_prefers_elevator_over_stairs(graph):
    """From a gate, step-free must pick the elevator/ramp edge, not stairs."""
    req = RouteRequest(origin="gate_C", destination="sec_114", step_free=True)
    result = graph.find_route(req)
    modes = {s.mode for s in result.steps}
    assert "stair" not in modes
    assert modes & {"elevator", "ramp"}


def test_non_step_free_may_use_stairs(graph):
    """The fastest unconstrained route from a gate should use the quick stair."""
    req = RouteRequest(origin="gate_C", destination="sec_114", step_free=False)
    result = graph.find_route(req)
    assert result.steps[0].mode == "stair"


def test_unknown_node_raises(graph):
    with pytest.raises(ValueError):
        graph.find_route(RouteRequest(origin="atlantis", destination="sec_114"))


def test_co2_optimization_prefers_low_carbon(graph):
    """Optimizing for CO2 should never pick a higher-CO2 total than time-opt."""
    green = graph.find_route(RouteRequest(origin="metro", destination="shuttle_hub", optimize="co2"))
    fast = graph.find_route(RouteRequest(origin="metro", destination="shuttle_hub", optimize="time"))
    assert green.total_co2 <= fast.total_co2


def test_congestion_changes_travel_time(graph):
    """A congested zone must increase the reported traversal time."""
    req = RouteRequest(origin="conc_N", destination="conc_E")
    free = graph.find_route(req, congestion={})
    jammed = graph.find_route(req, congestion={"ne": 1.5})
    assert jammed.total_time > free.total_time


def test_reported_time_matches_congestion_weighting(graph):
    """The time surfaced to the user must be the *same* congested time the search
    optimised over — not a silently recomputed (or stale) base time."""
    req = RouteRequest(origin="conc_N", destination="conc_E")
    jammed = graph.find_route(req, congestion={"ne": 1.5})
    assert jammed.total_time == pytest.approx(150 * 2.5)
    assert jammed.congestion_applied is True


def test_invalid_objective_rejected(graph):
    with pytest.raises(ValueError):
        graph.find_route(RouteRequest(origin="metro", destination="sec_114",
                                      optimize="teleport"))


def test_step_free_precomputed_on_edges(graph):
    """The accessibility flag is derived once at load, so the search loop never
    recomputes it. Stairs must never be marked step-free."""
    for edge in graph.edges:
        expected = edge.accessible and edge.mode not in STEP_MODES
        assert edge.step_free is expected


def test_adjacency_shares_edge_objects(graph):
    """Undirected edges are stored once and referenced from both endpoints,
    rather than allocating a mirrored copy per direction."""
    sample = graph.edges[0]
    fwd = [e for n, e in graph.neighbors(sample.frm) if e is sample]
    rev = [e for n, e in graph.neighbors(sample.to) if e is sample]
    assert fwd and rev, "both endpoints should reference the same Edge instance"


def test_route_is_immutable(graph):
    """Results are frozen so a caller cannot mutate a verified route.

    This matters for the safety story: once the engine has certified a path as
    step-free, no downstream layer (including the GenAI narrator) can edit it.
    """
    result = graph.find_route(RouteRequest(origin="gate_C", destination="sec_114"))
    assert isinstance(result.steps, tuple)
    assert isinstance(result.node_ids, tuple)
    with pytest.raises(FrozenInstanceError):
        result.steps[0].mode = "stair"
