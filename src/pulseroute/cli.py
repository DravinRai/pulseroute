"""PulseRoute command-line interface.

Examples:
  python -m pulseroute.cli route "from metro to section 114 in a wheelchair"
  python -m pulseroute.cli route "greenest way from metro to gate C" --minute 45
  python -m pulseroute.cli ops --minute 45
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .feed import FeedSimulator
from .graph import Graph, NoRouteError
from .llm_agent import LLMAgent
from .ops import build_brief

_DATA = Path(__file__).resolve().parents[2] / "data" / "stadium_graph.json"


def _load_graph(path: str | None) -> Graph:
    return Graph.from_json(path or _DATA)


def cmd_route(args: argparse.Namespace) -> int:
    graph = _load_graph(args.graph)
    agent = LLMAgent()
    feed = FeedSimulator()
    congestion = feed.snapshot(args.minute).factors if args.minute is not None else None
    try:
        request = agent.parse_request(args.query)
    except ValueError as e:
        print(f"Could not understand request: {e}", file=sys.stderr)
        return 2
    try:
        result = graph.find_route(request, congestion=congestion)
    except NoRouteError as e:
        print(str(e), file=sys.stderr)
        return 3
    print(agent.narrate(graph, result, language=args.lang))
    return 0


def cmd_ops(args: argparse.Namespace) -> int:
    feed = FeedSimulator()
    snapshot = feed.snapshot(args.minute)
    print(build_brief(snapshot).as_text())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pulseroute", description="Hybrid symbolic+GenAI stadium copilot.")
    p.add_argument("--graph", help="Path to a stadium graph JSON (defaults to bundled venue).")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("route", help="Fan wayfinding from a natural-language request.")
    r.add_argument("query", help="Natural-language routing request.")
    r.add_argument("--minute", type=int, default=None, help="Matchday minute for live congestion.")
    r.add_argument("--lang", default="en", help="Response language code (used only with an API key).")
    r.set_defaults(func=cmd_route)

    o = sub.add_parser("ops", help="Control-room congestion decision brief.")
    o.add_argument("--minute", type=int, default=0, help="Matchday minute.")
    o.set_defaults(func=cmd_ops)
    return p


def _force_utf8_stdout() -> None:
    """Ensure emoji/arrows render on any platform (e.g. Windows cp1252 consoles)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
