"""PulseRoute: Hybrid symbolic + GenAI stadium operations copilot.

Design invariant: GenAI parses intent and narrates results. It NEVER invents
routes. All navigation is deterministic A* over a ground-truth venue graph, so
safety-critical guidance (e.g. step-free routing) is provable, not hoped for.
"""

__version__ = "1.0.0"
