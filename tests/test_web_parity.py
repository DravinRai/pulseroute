"""Structural guards on the two-implementation boundary.

PulseRoute ships the routing engine twice: once in Python (the reference
implementation, exercised by the rest of this suite) and once in JavaScript so
the deployed demo is a static, key-less, zero-backend site.

Two implementations is a genuine divergence risk, so we contain it structurally
rather than by discipline:

1. **The venue is defined exactly once.** Both engines read the same
   ``docs/data/stadium_graph.json`` — Python from disk, the browser via
   ``fetch()``. These tests assert the web app never re-embeds a copy of that
   data, which is what previously allowed the two to drift.
2. **Shared constants are asserted equal.** Anything the algorithms must agree
   on (currently ``STEP_MODES``, the safety-critical one) is checked here.

Behavioural equivalence is verified separately and exhaustively: all 1,680
origin x destination x constraint x congestion combinations produce identical
routes in both engines.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pulseroute import VENUE_GRAPH_PATH
from pulseroute.graph import STEP_MODES

WEB_ROOT = Path(__file__).resolve().parents[1] / "docs"
INDEX = WEB_ROOT / "index.html"
JS_DIR = WEB_ROOT / "assets" / "js"


@pytest.fixture(scope="module")
def graph_js() -> str:
    return (JS_DIR / "graph.js").read_text(encoding="utf-8")


def test_venue_graph_lives_where_pages_can_serve_it():
    """The browser fetches this exact file, so it must sit inside the published
    site root. If it moves out of docs/, the live demo breaks."""
    assert VENUE_GRAPH_PATH.is_file()
    assert VENUE_GRAPH_PATH.parent == WEB_ROOT / "data"


def test_web_app_fetches_the_shared_venue_graph(graph_js):
    """The single source of truth is loaded, not duplicated."""
    assert "data/stadium_graph.json" in graph_js
    assert "fetch(" in graph_js


def test_web_app_does_not_embed_venue_data(graph_js):
    """Regression guard: the venue graph used to be pasted into the page as a JS
    literal, which let the copy drift from the JSON (it did — a node label went
    stale). Fetching the shared file is what makes drift impossible, so no module
    may reintroduce an embedded node/edge table."""
    node_ids = {n["id"] for n in json.loads(VENUE_GRAPH_PATH.read_text(encoding="utf-8"))["nodes"]}
    for module in sorted(JS_DIR.glob("*.js")):
        source = module.read_text(encoding="utf-8")
        if module.name in {"mapview.js", "nlu.js"}:
            continue  # legitimately reference ids for layout / aliases
        embedded = {nid for nid in node_ids if f'"{nid}"' in source}
        assert not embedded, f"{module.name} embeds venue data: {sorted(embedded)}"


def test_step_modes_match_python(graph_js):
    """The safety-critical constant must be identical in both implementations."""
    match = re.search(r"STEP_MODES\s*=\s*new Set\((\[[^\]]*\])\)", graph_js)
    assert match, "could not locate STEP_MODES in graph.js"
    assert set(json.loads(match.group(1))) == set(STEP_MODES)


def test_index_html_has_no_inline_style_or_script():
    """Markup, styling and behaviour stay in separate files."""
    html = INDEX.read_text(encoding="utf-8")
    assert "<style>" not in html
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "inline <script> block found"


def test_every_venue_node_has_map_coordinates():
    """A node with no layout entry would silently vanish from the map."""
    node_ids = {n["id"] for n in json.loads(VENUE_GRAPH_PATH.read_text(encoding="utf-8"))["nodes"]}
    mapview = (JS_DIR / "mapview.js").read_text(encoding="utf-8")
    layout_block = mapview[mapview.index("export const LAYOUT"):]
    missing = [nid for nid in node_ids if f"{nid}:" not in layout_block]
    assert not missing, f"nodes missing from the map layout: {missing}"
