"""PulseRoute: Hybrid symbolic + GenAI stadium operations copilot.

Design invariant: GenAI parses intent and narrates results. It NEVER invents
routes. All navigation is deterministic graph search over a ground-truth venue
graph, so safety-critical guidance (e.g. step-free routing) is provable, not
hoped for.
"""
from pathlib import Path

__version__ = "1.1.0"

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: The single source of truth for the venue.
#:
#: It lives under ``docs/`` because GitHub Pages publishes that directory as the
#: site root, which lets the browser ``fetch()`` this exact file. The Python
#: engine and the web app therefore read the *same* JSON — the venue is defined
#: once, so the two implementations cannot drift apart on the data.
VENUE_GRAPH_PATH = _REPO_ROOT / "docs" / "data" / "stadium_graph.json"

__all__ = ["VENUE_GRAPH_PATH", "__version__"]
