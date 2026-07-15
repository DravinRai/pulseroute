"""Guards the one real duplication in this project.

The deployed web app (`docs/index.html`) must run the same venue graph as the
Python reference implementation, but it embeds that graph as a JS literal so the
demo stays a single self-contained file with no fetch/CORS dependency.

Duplicated data is a divergence risk, so we make divergence a *test failure*
rather than a latent bug: these tests parse the graph back out of the shipped
HTML and assert it matches `data/stadium_graph.json` exactly.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "docs" / "index.html"
DATA = ROOT / "data" / "stadium_graph.json"


def _extract_js_array(source: str, key: str) -> list:
    """Pull `key:[ ... ]` out of the embedded GRAPH literal via bracket matching.

    The arrays are JSON-compatible by construction (double-quoted strings,
    numeric literals, `null`), so once the exact span is isolated we can hand it
    to json.loads rather than trusting a regex to parse nested brackets.
    """
    marker = f"{key}:["
    start = source.index(marker) + len(marker) - 1
    depth = 0
    for i in range(start, len(source)):
        ch = source[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return json.loads(source[start:i + 1])
    raise AssertionError(f"Unbalanced brackets while extracting {key!r}")


@pytest.fixture(scope="module")
def web_graph() -> dict:
    source = WEB.read_text(encoding="utf-8")
    return {
        "nodes": _extract_js_array(source, "nodes"),
        "edges": _extract_js_array(source, "edges"),
    }


@pytest.fixture(scope="module")
def json_graph() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_web_app_nodes_match_reference_graph(web_graph, json_graph):
    web = {(n[0], n[1], n[2]) for n in web_graph["nodes"]}
    ref = {(n["id"], n["label"], n["type"]) for n in json_graph["nodes"]}
    assert web == ref, "docs/index.html nodes have drifted from stadium_graph.json"


def test_web_app_edges_match_reference_graph(web_graph, json_graph):
    web = {
        (e[0], e[1], e[2], bool(e[3]), float(e[4]), float(e[5]), float(e[6]), e[7])
        for e in web_graph["edges"]
    }
    ref = {
        (e["from"], e["to"], e["mode"], bool(e["accessible"]), float(e["distance"]),
         float(e["co2"]), float(e["base_time"]), e.get("congestion_zone"))
        for e in json_graph["edges"]
    }
    assert web == ref, "docs/index.html edges have drifted from stadium_graph.json"


def test_web_app_step_modes_match_python():
    """The safety-critical constant must be identical in both implementations."""
    from pulseroute.graph import STEP_MODES

    source = WEB.read_text(encoding="utf-8")
    line = next(ln for ln in source.splitlines() if "STEP_MODES" in ln and "new Set" in ln)
    web_modes = set(json.loads(line[line.index("["):line.index("]") + 1]))
    assert web_modes == set(STEP_MODES)
