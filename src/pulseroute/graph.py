"""Venue graph model and constraint-aware A* search.

This module is intentionally free of any AI / LLM code. It is pure, deterministic,
and unit-testable. If this module says a route exists, it exists in the venue.
"""
from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Vertical-transition modes that require stepping / are not wheelchair-usable.
STEP_MODES = frozenset({"stair", "escalator"})


@dataclass(frozen=True)
class Edge:
    frm: str
    to: str
    mode: str
    accessible: bool
    distance: float          # meters
    co2: float               # grams (transit legs only; walking is 0)
    base_time: float         # seconds, uncongested
    congestion_zone: str | None = None

    def is_step_free(self) -> bool:
        return self.accessible and self.mode not in STEP_MODES


@dataclass(frozen=True)
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

    def validate(self, graph: "Graph") -> None:
        if self.origin not in graph.nodes:
            raise ValueError(f"Unknown origin node: {self.origin!r}")
        if self.destination not in graph.nodes:
            raise ValueError(f"Unknown destination node: {self.destination!r}")
        if self.optimize not in {"time", "co2", "balanced"}:
            raise ValueError(f"Unknown optimize objective: {self.optimize!r}")


@dataclass
class RouteStep:
    frm: str
    to: str
    mode: str
    label_to: str
    distance: float
    time: float
    co2: float


@dataclass
class RouteResult:
    steps: list[RouteStep]
    total_distance: float
    total_time: float
    total_co2: float
    step_free: bool
    optimize: str
    congestion_applied: bool

    @property
    def node_ids(self) -> list[str]:
        if not self.steps:
            return []
        return [self.steps[0].frm] + [s.to for s in self.steps]


class NoRouteError(Exception):
    """Raised when no path satisfies the request's hard constraints."""


class Graph:
    def __init__(self, nodes: dict[str, Node], edges: list[Edge],
                 external_arrival: dict | None = None):
        self.nodes = nodes
        self.edges = edges
        self.external_arrival = external_arrival or {}
        self._adj: dict[str, list[Edge]] = {n: [] for n in nodes}
        for e in edges:
            # Graph is undirected: every edge is traversable both ways.
            self._adj[e.frm].append(e)
            self._adj[e.to].append(
                Edge(e.to, e.frm, e.mode, e.accessible, e.distance,
                     e.co2, e.base_time, e.congestion_zone)
            )

    # ---- loading -------------------------------------------------------
    @classmethod
    def from_json(cls, path: str | Path) -> "Graph":
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

    def neighbors(self, node_id: str) -> Iterable[Edge]:
        return self._adj.get(node_id, ())

    # ---- routing -------------------------------------------------------
    def find_route(self, request: RouteRequest,
                   congestion: dict[str, float] | None = None) -> RouteResult:
        """Constraint-aware A* (Dijkstra with zero heuristic — admissible and
        exact for this small graph). Hard constraints prune edges BEFORE search,
        so an impossible-for-the-user edge can never appear in the result."""
        request.validate(self)
        congestion = congestion or {}

        def edge_allowed(e: Edge) -> bool:
            # HARD accessibility constraint: step-free removes stairs/escalators
            # and any edge not flagged accessible. This is why we can prove a
            # wheelchair route never contains a staircase.
            if request.step_free and not e.is_step_free():
                return False
            return True

        def edge_cost(e: Edge) -> float:
            time = e.base_time
            congestion_applied = False
            if request.avoid_congestion and e.congestion_zone:
                factor = congestion.get(e.congestion_zone, 0.0)
                if factor:
                    time *= (1.0 + factor)   # congestion inflates traversal time
                    congestion_applied = True
            if request.optimize == "time":
                cost = time
            elif request.optimize == "co2":
                # Prefer low-carbon; keep a small time term to break ties.
                cost = e.co2 * 10.0 + time * 0.01
            else:  # balanced
                cost = time + e.co2 * 2.0
            return cost, congestion_applied  # type: ignore[return-value]

        # Dijkstra
        dist: dict[str, float] = {request.origin: 0.0}
        prev: dict[str, tuple[str, Edge]] = {}
        pq: list[tuple[float, str]] = [(0.0, request.origin)]
        any_congestion = False

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, math.inf):
                continue
            if u == request.destination:
                break
            for e in self.neighbors(u):
                if not edge_allowed(e):
                    continue
                cost, capp = edge_cost(e)
                any_congestion = any_congestion or capp
                nd = d + cost
                if nd < dist.get(e.to, math.inf):
                    dist[e.to] = nd
                    prev[e.to] = (u, e)
                    heapq.heappush(pq, (nd, e.to))

        if request.destination not in dist:
            reason = ("no step-free path exists under current constraints"
                      if request.step_free else "no path exists")
            raise NoRouteError(
                f"Cannot route {request.origin} -> {request.destination}: {reason}."
            )

        # Reconstruct
        steps: list[RouteStep] = []
        cur = request.destination
        while cur != request.origin:
            u, e = prev[cur]
            t = e.base_time
            if request.avoid_congestion and e.congestion_zone:
                t *= (1.0 + congestion.get(e.congestion_zone, 0.0))
            steps.append(RouteStep(
                frm=u, to=cur, mode=e.mode, label_to=self.nodes[cur].label,
                distance=e.distance, time=t, co2=e.co2,
            ))
            cur = u
        steps.reverse()

        return RouteResult(
            steps=steps,
            total_distance=sum(s.distance for s in steps),
            total_time=sum(s.time for s in steps),
            total_co2=sum(s.co2 for s in steps),
            step_free=request.step_free,
            optimize=request.optimize,
            congestion_applied=any_congestion,
        )
