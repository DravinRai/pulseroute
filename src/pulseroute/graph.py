"""Venue graph model and constraint-aware shortest-path search.

This module is intentionally free of any AI / LLM code. It is pure, deterministic,
and unit-testable. If this module says a route exists, it exists in the venue.

Algorithm & complexity
----------------------
Routing is **Dijkstra's algorithm** over a binary heap: ``O((V + E) log V)`` time,
``O(V)`` space. Hard constraints are applied as edge filters during relaxation, so
a forbidden edge is never even considered.

Why not A*? A* only beats Dijkstra when an *admissible* heuristic is available —
one that provably never overestimates the remaining cost. Our venue coordinates
are schematic (drawn for legibility, not to scale), so a straight-line distance
heuristic would not be admissible against the real ``distance``/``base_time``
fields. An inadmissible heuristic can silently return a non-optimal path, which
for a step-free route means quietly handing a wheelchair user a worse detour.
Dijkstra (equivalently, A* with a zero heuristic) is exact, and on a venue-sized
graph the constant-factor win from a heuristic is irrelevant. Correctness first.
"""
from __future__ import annotations

import heapq
import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Vertical-transition modes that require stepping / are not wheelchair-usable.
STEP_MODES = frozenset({"stair", "escalator"})

# Objective weights. Kept as named constants so the cost model is inspectable
# rather than buried in magic numbers inside the search loop.
_CO2_WEIGHT_GREEN = 10.0   # grams -> cost, when optimising for carbon
_TIME_TIEBREAK_GREEN = 0.01
_CO2_WEIGHT_BALANCED = 2.0

OPTIMIZE_OBJECTIVES = frozenset({"time", "co2", "balanced"})


@dataclass(frozen=True, slots=True)
class Edge:
    frm: str
    to: str
    mode: str
    accessible: bool
    distance: float          # meters
    co2: float               # grams (transit legs only; walking is 0)
    base_time: float         # seconds, uncongested
    congestion_zone: str | None = None
    # Derived once at construction; read on every relaxation, so precomputing it
    # keeps a frozenset lookup out of the inner search loop.
    step_free: bool = field(init=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "step_free", self.accessible and self.mode not in STEP_MODES
        )


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    label: str
    level: str
    type: str


@dataclass
class RouteRequest:
    """Structured intent. Produced by the LLM NLU layer OR by hand in tests."""
    origin: str
    destination: str
    step_free: bool = False              # hard accessibility constraint
    optimize: str = "time"               # "time" | "co2" | "balanced"
    avoid_congestion: bool = True

    def validate(self, graph: Graph) -> None:
        if self.origin not in graph.nodes:
            raise ValueError(f"Unknown origin node: {self.origin!r}")
        if self.destination not in graph.nodes:
            raise ValueError(f"Unknown destination node: {self.destination!r}")
        if self.optimize not in OPTIMIZE_OBJECTIVES:
            raise ValueError(f"Unknown optimize objective: {self.optimize!r}")


@dataclass(frozen=True, slots=True)
class RouteStep:
    frm: str
    to: str
    mode: str
    label_to: str
    distance: float
    time: float
    co2: float


@dataclass(frozen=True, slots=True)
class RouteResult:
    steps: tuple[RouteStep, ...]
    total_distance: float
    total_time: float
    total_co2: float
    step_free: bool
    optimize: str
    congestion_applied: bool
    node_ids: tuple[str, ...]


class NoRouteError(Exception):
    """Raised when no path satisfies the request's hard constraints."""


class Graph:
    """An undirected venue graph with O(1) neighbour lookup.

    Adjacency stores ``(neighbour_id, edge)`` pairs that reference the *same*
    ``Edge`` object from both endpoints, rather than allocating a mirrored copy
    per direction. Edge attributes (distance, time, CO2) are direction-agnostic,
    so one object per physical edge is both correct and half the memory.
    """

    def __init__(self, nodes: dict[str, Node], edges: list[Edge],
                 external_arrival: dict[str, Any] | None = None):
        self.nodes = nodes
        self.edges = edges
        self.external_arrival = external_arrival or {}
        adj: dict[str, list[tuple[str, Edge]]] = {n: [] for n in nodes}
        for e in edges:
            adj[e.frm].append((e.to, e))
            adj[e.to].append((e.frm, e))
        # Freeze to tuples: adjacency never changes after load, and tuples are
        # cheaper to iterate than lists.
        self._adj: dict[str, tuple[tuple[str, Edge], ...]] = {
            k: tuple(v) for k, v in adj.items()
        }

    # ---- loading -------------------------------------------------------
    @classmethod
    def from_json(cls, path: str | Path) -> Graph:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        nodes = {
            n["id"]: Node(n["id"], n["label"], n["level"], n["type"])
            for n in data["nodes"]
        }
        edges = [
            Edge(
                e["from"], e["to"], e["mode"], bool(e["accessible"]),
                float(e["distance"]), float(e["co2"]), float(e["base_time"]),
                e.get("congestion_zone"),
            )
            for e in data["edges"]
        ]
        return cls(nodes, edges, data.get("external_arrival"))

    def neighbors(self, node_id: str) -> tuple[tuple[str, Edge], ...]:
        return self._adj.get(node_id, ())

    # ---- cost model ----------------------------------------------------
    @staticmethod
    def _make_cost_fn(
        request: RouteRequest, congestion: dict[str, float]
    ) -> Callable[[Edge], tuple[float, float, bool]]:
        """Build the per-edge cost function once, outside the search loop.

        Returns ``(search_cost, real_time, congestion_applied)``. Returning the
        real traversal time alongside the search cost means the reconstruction
        pass can reuse it instead of recomputing the congestion maths — the
        weights are applied exactly once per edge, in one place.
        """
        optimize = request.optimize
        avoid = request.avoid_congestion

        def cost(edge: Edge) -> tuple[float, float, bool]:
            time = edge.base_time
            applied = False
            zone = edge.congestion_zone
            if avoid and zone:
                factor = congestion.get(zone, 0.0)
                if factor:
                    time *= 1.0 + factor      # congestion inflates traversal time
                    applied = True
            if optimize == "time":
                search_cost = time
            elif optimize == "co2":
                # Prefer low-carbon; keep a small time term to break ties.
                search_cost = edge.co2 * _CO2_WEIGHT_GREEN + time * _TIME_TIEBREAK_GREEN
            else:  # balanced
                search_cost = time + edge.co2 * _CO2_WEIGHT_BALANCED
            return search_cost, time, applied

        return cost

    # ---- routing -------------------------------------------------------
    def find_route(self, request: RouteRequest,
                   congestion: dict[str, float] | None = None) -> RouteResult:
        """Constraint-aware Dijkstra. ``O((V + E) log V)``.

        Hard constraints prune edges *during relaxation*, so an edge the user
        cannot physically use is never placed on the frontier and therefore can
        never appear in the result. This is what makes step-free routing a
        structural guarantee rather than a post-hoc filter.
        """
        request.validate(self)
        congestion = congestion or {}
        cost_fn = self._make_cost_fn(request, congestion)
        step_free_only = request.step_free

        origin, destination = request.origin, request.destination
        dist: dict[str, float] = {origin: 0.0}
        prev: dict[str, tuple[str, Edge, float]] = {}
        visited: set[str] = set()
        frontier: list[tuple[float, str]] = [(0.0, origin)]
        congestion_applied = False

        while frontier:
            d, u = heapq.heappop(frontier)
            if u in visited:
                continue          # stale heap entry (lazy deletion)
            visited.add(u)
            if u == destination:
                break
            for v, edge in self._adj[u]:
                # HARD accessibility constraint.
                if step_free_only and not edge.step_free:
                    continue
                search_cost, real_time, applied = cost_fn(edge)
                if applied:
                    congestion_applied = True
                nd = d + search_cost
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = (u, edge, real_time)
                    heapq.heappush(frontier, (nd, v))

        if destination not in dist:
            reason = ("no step-free path exists under current constraints"
                      if step_free_only else "no path exists")
            raise NoRouteError(
                f"Cannot route {origin} -> {destination}: {reason}."
            )

        return self._build_result(request, prev, congestion_applied)

    def _build_result(self, request: RouteRequest,
                      prev: dict[str, tuple[str, Edge, float]],
                      congestion_applied: bool) -> RouteResult:
        """Walk the predecessor chain back to the origin and total it up."""
        steps: list[RouteStep] = []
        cur = request.destination
        while cur != request.origin:
            u, edge, real_time = prev[cur]
            steps.append(RouteStep(
                frm=u, to=cur, mode=edge.mode, label_to=self.nodes[cur].label,
                distance=edge.distance, time=real_time, co2=edge.co2,
            ))
            cur = u
        steps.reverse()

        node_ids = (request.origin, *(s.to for s in steps)) if steps else (request.origin,)
        return RouteResult(
            steps=tuple(steps),
            total_distance=math.fsum(s.distance for s in steps),
            total_time=math.fsum(s.time for s in steps),
            total_co2=math.fsum(s.co2 for s in steps),
            step_free=request.step_free,
            optimize=request.optimize,
            congestion_applied=congestion_applied,
            node_ids=node_ids,
        )
