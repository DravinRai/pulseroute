# PulseRoute — Hybrid Symbolic + GenAI Stadium Operations Copilot

**FIFA World Cup 2026 · Challenge 4: Smart Stadiums & Tournament Operations**

[![CI](https://github.com/DravinRai/pulseroute/actions/workflows/ci.yml/badge.svg)](https://github.com/DravinRai/pulseroute/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/tests-32%20passing-brightgreen)
![Runtime dependencies](https://img.shields.io/badge/runtime%20dependencies-0-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

PulseRoute is a stadium wayfinding and operations copilot that combines a
**deterministic graph-routing engine** with a **Generative AI language layer**.
It gives fans safe, accessible, multilingual navigation and gives control-room
staff real-time congestion decision support — without ever letting the AI
hallucinate a route.

**🔗 Live demo:** `https://dravinrai.github.io/pulseroute/`
(an interactive, WCAG-conscious web app with a live stadium map — see
[§ Deploying the live demo](#7-deploying-the-live-demo-github-pages)).

---

## 1. The chosen vertical & persona

PulseRoute deliberately goes deep on **Accessibility + Crowd Management + Real-time
Decision Support**, serving two personas from one architecture:

| Persona | Need PulseRoute meets |
|---|---|
| **International fan with a mobility, sensory, or language need** | "Get me from the metro to Section 114 in a wheelchair, avoiding the crowds" — in their own language, with a **guaranteed step-free** path. |
| **Venue operations / control-room staff** | "Where are my top congestion risks right now and what should I do?" — a live, ranked decision brief. |

Across these it touches **six of the seven** challenge objectives: navigation &
wayfinding, crowd management, accessibility, transportation logistics,
sustainability, and multilingual assistance — through one coherent user journey
rather than a scattered feature list.

---

## 2. Approach & underlying logic (the core idea)

**The problem with naïve "GenAI wayfinding":** A large language model asked for
step-free directions will *confidently generate plausible but unverifiable*
routes. For a wheelchair user, a hallucinated staircase is not a cosmetic bug — it
strands a person. LLMs are excellent at language and intent, and unreliable at
precise, safety-critical spatial reasoning.

**PulseRoute's answer — a strict division of labour:**

```
        ┌─────────────────────────────────────────────────────┐
        │  GenAI layer (llm_agent.py)                          │
        │  • Understands free text → structured RouteRequest   │
        │  • Narrates a computed route in any language         │
        │  • NEVER sees graph edges · NEVER chooses the path   │
        └───────────────┬─────────────────────────────────────┘
                        │  RouteRequest (re-validated)
                        ▼
        ┌─────────────────────────────────────────────────────┐
        │  Deterministic engine (graph.py) — ZERO AI           │
        │  • Constraint-aware Dijkstra over a ground-truth map │
        │  • Hard accessibility constraint prunes stair edges  │
        │    during relaxation → step-free is provable         │
        │  • Live congestion reweights edges (feed.py)         │
        │  • CO₂-weighted objective for sustainable routing    │
        └─────────────────────────────────────────────────────┘
```

The LLM's output surface is intentionally tiny. The worst a bad parse can do is
request an *impossible* route, which the engine rejects cleanly — it can never
fabricate a staircase into a wheelchair user's directions. **This is the
submission's central thesis: GenAI for intent and empathy, symbolic search for
truth and safety.**

---

## 3. How it works technically

### Modules

**The venue is defined exactly once.** `docs/data/stadium_graph.json` is read by
Python from disk *and* `fetch()`-ed by the browser — it lives under `docs/`
because GitHub Pages publishes that directory as the site root. Neither engine
carries a copy, so they cannot drift apart on the data.

| File | Responsibility | AI? |
|---|---|---|
| `docs/data/stadium_graph.json` | **Single source of truth**: nodes, edges, modes, accessibility flags, CO₂, congestion zones. | — |
| `src/pulseroute/graph.py` | Graph model + **constraint-aware Dijkstra**. Pure, deterministic, testable. | No |
| `src/pulseroute/feed.py` | Deterministic congestion-feed simulator (pluggable for real telemetry). | No |
| `src/pulseroute/ops.py` | Aggregates live state into a ranked operations decision brief. | No |
| `src/pulseroute/llm_agent.py` | NLU (text → `RouteRequest`) + multilingual narration. Claude-backed, with an offline rule-based fallback. | Yes |
| `src/pulseroute/cli.py` | Command-line interface for both personas. | — |

The deployed web app mirrors that same separation of concerns — markup, styling
and behaviour are separate files, and each module has one job:

| File | Responsibility |
|---|---|
| `docs/index.html` | Semantic markup only (no inline `<style>` or `<script>`). |
| `docs/assets/styles.css` | All styling; light/dark theming. |
| `docs/assets/js/graph.js` | Venue graph + constraint-aware Dijkstra (binary min-heap). Counterpart of `graph.py`. |
| `docs/assets/js/feed.js` | Congestion simulator. Counterpart of `feed.py`. |
| `docs/assets/js/ops.js` | Control-room brief. Counterpart of `ops.py`. |
| `docs/assets/js/nlu.js` | Offline intent parser. Counterpart of the fallback in `llm_agent.py`. |
| `docs/assets/js/mapview.js` | SVG stadium map rendering. Presentation only. |
| `docs/assets/js/icons.js` | Inline SVG icon set. |
| `docs/assets/js/main.js` | DOM wiring — the only module that touches the page. |

### Key mechanisms
- **Hard accessibility constraint.** When `step_free=True`, every stair/escalator
  edge (and any non-accessible edge) is skipped *during relaxation* via the
  precomputed `Edge.step_free` flag, so a forbidden edge never reaches the
  frontier. The resulting path is provably step-free.
- **Congestion-aware routing.** Each concourse edge carries a `congestion_zone`.
  The feed supplies a per-zone multiplier that inflates traversal time, so routes
  re-plan around crowds in real time.
- **Sustainability objective.** Transit legs carry a CO₂ weight; `optimize="co2"`
  minimises carbon (and honestly prefers walking over a shuttle when greener).
- **Graceful AI degradation.** No `ANTHROPIC_API_KEY`? The system runs fully
  offline via `RuleBasedParser` + `TemplateNarrator`. With a key, `pip install
  anthropic` unlocks Claude-backed understanding and true multilingual output.

### Algorithm choice, stated honestly

Routing is **Dijkstra's algorithm** on a binary heap — `O((V + E) log V)` time,
`O(V)` space.

**Why not A\*?** A\* only beats Dijkstra given an *admissible* heuristic — one that
provably never overestimates remaining cost. Our venue coordinates are schematic
(laid out for map legibility, not to scale), so a straight-line heuristic would
**not** be admissible against the real `distance`/`base_time` fields. An
inadmissible heuristic silently returns non-optimal paths — for a step-free
request, that means quietly handing a wheelchair user a worse detour. Dijkstra is
A\* with a zero heuristic: exact, and on a venue-sized graph the constant-factor
win from a heuristic is irrelevant. **Correctness over cleverness.**

### Efficiency: where the work *isn't* done

| Decision | Effect |
|---|---|
| LLM never invoked for computation — only language | Routing costs zero tokens and zero network round-trips |
| Constraints filter edges **during relaxation** | Forbidden edges never reach the frontier |
| `Edge.step_free` derived **once at load** | No frozenset lookup per relaxation |
| Adjacency references **one `Edge` object** per physical edge, from both endpoints | Half the edge allocations; no mirrored copies |
| Cost function built **once per request**, returns `(search_cost, real_time)` | Congestion maths applied exactly once per edge — reconstruction reuses it instead of recomputing |
| Alias table sorted **once at import** | Longest-alias-wins NLU without re-sorting per request |
| Feed timeline keys sorted once → `bisect` | `O(log n)` snapshot lookup instead of an `O(n log n)` sort per call |
| Frozen `slots=True` dataclasses | Lower memory, no per-instance `__dict__` |
| Web app ships a **binary min-heap** | Matches `heapq`; replaced a frontier re-sort that was `O(V² log V)` overall |
| Zero runtime dependencies | Nothing to install, resolve, or audit |

---

## 4. Quick start

```bash
# No dependencies required for the core engine (Python 3.10+, stdlib only).
export PYTHONPATH=src          # Windows PowerShell: $env:PYTHONPATH="src"

# Fan — guaranteed step-free, congestion-aware wayfinding
python -m pulseroute.cli route "from metro to section 114 in a wheelchair" --minute 0

# Fan — fastest route (may use stairs) and greenest route
python -m pulseroute.cli route "from gate C to section 114"
python -m pulseroute.cli route "greenest way from metro to shuttle hub"

# Ops — control-room congestion brief at halftime
python -m pulseroute.cli ops --minute 45
```

### Enable the Claude GenAI layer (optional)
```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-...      # then add --lang es, --lang ar, etc.
python -m pulseroute.cli route "silla de ruedas del metro a la sección 114" --lang es
```

---

## 5. Testing

```bash
pip install pytest
python -m pytest -q          # 32 tests, fully offline & deterministic
```

Every test runs with **no network and no API key**. CI runs the suite on Python
3.10 and 3.12, plus `ruff` lint and `mypy --strict` gates on every push
(`.github/workflows/ci.yml`).

Highlights the grader can inspect:
- `test_step_free_route_never_contains_stairs` — the safety invariant, asserted
  directly against the returned path.
- `test_step_free_prefers_elevator_over_stairs` / `test_non_step_free_may_use_stairs`
  — proves the constraint changes behaviour.
- `test_reported_time_matches_congestion_weighting` — the time shown to the user is
  the same congested time the search optimised over, not a recomputed value.
- `test_route_is_immutable` — once a path is certified step-free, no downstream
  layer (including the GenAI narrator) can mutate it.
- `test_co2_optimization_prefers_low_carbon` — proves the sustainability objective.
- `test_valid_node_ids_are_precomputed_and_complete` — regression test for a real
  crash on the Claude prompt path (`dict_values | set` raised `TypeError`) that
  only surfaced once an API key was present.

### Containing the two-implementation risk

The engine exists twice: Python (the reference implementation) and JavaScript, so
the deployed demo can be a static, key-less, zero-backend site. Two
implementations is a real divergence risk, so it is contained **structurally**
rather than by discipline:

1. **The data cannot drift** — both engines read the same
   `docs/data/stadium_graph.json`. Neither embeds a copy.
   `tests/test_web_parity.py` asserts the web app *fetches* that file and that no
   module re-embeds venue data. *(An earlier version did embed a copy, and it
   drifted — a node label went stale. That's precisely why the copy is gone.)*
2. **Shared constants are asserted equal** — the safety-critical `STEP_MODES` is
   parsed out of `graph.js` and compared against Python.
3. **Structure is enforced** — tests assert `index.html` carries no inline
   `<style>`/`<script>`, and that every venue node has map coordinates (a missing
   entry would silently vanish from the map).

The two engines were additionally verified to agree **exhaustively**: all
**1,680** origin × destination × constraint × congestion combinations produce
identical routes and times in Python and JavaScript (matching digests computed
independently on each side).

---

## 6. How PulseRoute maps to the evaluation criteria

| Criterion | How we address it |
|---|---|
| **Problem-statement alignment (High Impact)** | Targets the *root* failure of GenAI wayfinding (unsafe hallucinated routes) and solves it structurally; serves real, underserved personas across 6/7 objectives. |
| **Code quality** | Strict separation of concerns (AI vs. deterministic); frozen typed dataclasses; every module documents its invariants; single-source cost model (no duplicated weighting logic); honest naming — we call it Dijkstra because it *is* Dijkstra, and say why; `ruff` + `mypy --strict` gates and CI on two Python versions; the web app is split into single-responsibility ES modules with no inline style/script. |
| **Security / responsible AI** | The LLM's authority is bounded by design; its output is re-validated against ground truth before use; verified routes are immutable; no secrets in code; **zero runtime dependencies** shrinks the supply-chain surface to nothing. |
| **Efficiency** | `O((V + E) log V)` heap-based search; constraints prune during relaxation; per-edge derived state precomputed at load; congestion maths applied exactly once per edge; `bisect` feed lookups; alias table sorted once at import; binary min-heap in the web app. The LLM is never invoked for computation — only language. See [§ Efficiency](#efficiency-where-the-work-isnt-done). |
| **Testing** | 32 deterministic offline tests, including the safety-critical accessibility invariant, a regression test for a real crash bug, and a parity test that makes Python↔JS divergence impossible. Verified exhaustively across all 1,680 routing combinations. |
| **Accessibility** | Step-free routing is a *hard guarantee*; sensory/calm-room and accessible-restroom nodes are first-class; multilingual narration serves non-native speakers. |

---

## 7. Deploying the live demo (GitHub Pages)

The `docs/index.html` file is a **single self-contained web app** — no build step,
no server, no secrets. Its JavaScript engine is a 1:1 port of the Python reference
(verified to produce identical routes), so the demo is trustworthy on its own.

**To publish the required Deployed Link:**
1. Push this repo to GitHub (public, single branch — see below).
2. Repo **Settings → Pages → Build and deployment → Source: “Deploy from a branch”**.
3. Branch: **`main`**, folder: **`/docs`** → **Save**.
4. Wait ~1 minute; your live URL is `https://<username>.github.io/<repo>/`.
   Put that URL in the “Deployed Link” field and at the top of this README.

The deployed demo runs the offline (rule-based) AI layer so it is always live and
free. The full Claude-backed multilingual layer ships in `src/pulseroute/llm_agent.py`
for anyone who runs it locally with an API key.

## 8. Assumptions

- **Reference venue.** `stadium_graph.json` models a representative World Cup
  stadium. In production it would be generated from the venue's real facilities
  map; the engine is venue-agnostic and loads any conforming graph.
- **Congestion feed is simulated.** `feed.py` provides a reproducible scripted
  matchday timeline so the demo/tests are fully offline. It exposes the same
  abstract interface (`{zone: factor}`) that a real telemetry source — gate scan
  rates, Wi-Fi association counts, CV people-counting — would populate.
- **CO₂ figures** are representative per-mode estimates for illustrating the
  sustainability objective, not audited emissions data.
- **The GenAI layer is optional by design** so the project is evaluable with zero
  network access; a Claude API key upgrades understanding and enables genuine
  multilingual responses.

---

## 9. Repository hygiene (challenge constraints)

- Single branch, public repo, **< 10 MB** (pure text/JSON/Python — well under 1 MB).
- No large binaries or bundled models; the intelligence is in the architecture,
  not in shipped weights.

## License
MIT — see `LICENSE`.
