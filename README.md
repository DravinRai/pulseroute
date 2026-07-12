# PulseRoute — Hybrid Symbolic + GenAI Stadium Operations Copilot

**FIFA World Cup 2026 · Challenge 4: Smart Stadiums & Tournament Operations**

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
        │  • Constraint-aware A* over a ground-truth venue graph│
        │  • Hard accessibility constraint prunes stair edges  │
        │    BEFORE search → step-free is provable, not hoped  │
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
| File | Responsibility | AI? |
|---|---|---|
| `data/stadium_graph.json` | Ground-truth venue graph: nodes, edges, modes, accessibility flags, CO₂, congestion zones. | — |
| `src/pulseroute/graph.py` | Graph model + **constraint-aware A*/Dijkstra**. Pure, deterministic, testable. | No |
| `src/pulseroute/feed.py` | Deterministic congestion-feed simulator (pluggable for real telemetry). | No |
| `src/pulseroute/ops.py` | Aggregates live state into a ranked operations decision brief. | No |
| `src/pulseroute/llm_agent.py` | NLU (text → `RouteRequest`) + multilingual narration. Claude-backed, with an offline rule-based fallback. | Yes |
| `src/pulseroute/cli.py` | Command-line interface for both personas. | — |
| `docs/index.html` | Self-contained web app (the deployed demo): the engine ported to JS, embedded graph, interactive stadium map. Served free via GitHub Pages. | Offline AI layer |

### Key mechanisms
- **Hard accessibility constraint.** When `step_free=True`, every stair/escalator
  edge (and any non-accessible edge) is filtered out *before* search runs
  (`Edge.is_step_free()`). The resulting path is provably step-free.
- **Congestion-aware routing.** Each concourse edge carries a `congestion_zone`.
  The feed supplies a per-zone multiplier that inflates traversal time, so routes
  re-plan around crowds in real time.
- **Sustainability objective.** Transit legs carry a CO₂ weight; `optimize="co2"`
  minimises carbon (and honestly prefers walking over a shuttle when greener).
- **Graceful AI degradation.** No `ANTHROPIC_API_KEY`? The system runs fully
  offline via `RuleBasedParser` + `TemplateNarrator`. With a key, `pip install
  anthropic` unlocks Claude-backed understanding and true multilingual output.

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
python -m pytest -q          # 17 tests, fully offline & deterministic
```

Highlights the grader can inspect:
- `test_step_free_route_never_contains_stairs` — the safety invariant, asserted
  directly against the returned path.
- `test_step_free_prefers_elevator_over_stairs` / `test_non_step_free_may_use_stairs`
  — proves the constraint changes behaviour.
- `test_congestion_changes_travel_time` — proves live reweighting works.
- `test_co2_optimization_prefers_low_carbon` — proves the sustainability objective.
- `test_parser_longest_alias_wins` — NLU disambiguation edge case.

---

## 6. How PulseRoute maps to the evaluation criteria

| Criterion | How we address it |
|---|---|
| **Problem-statement alignment (High Impact)** | Targets the *root* failure of GenAI wayfinding (unsafe hallucinated routes) and solves it structurally; serves real, underserved personas across 6/7 objectives. |
| **Code quality** | Strict separation of concerns (AI vs. deterministic), typed dataclasses, docstrings stating invariants, no god-objects. |
| **Security / responsible AI** | The LLM's authority is bounded by design; its output is re-validated against ground truth; no secrets in code; zero required third-party deps shrinks supply-chain surface. |
| **Efficiency** | Routing is cheap graph search over a small graph — the LLM is never invoked for computation, only language. Runs offline with no dependencies. |
| **Testing** | 17 deterministic tests, including explicit assertions of the safety-critical accessibility invariant. |
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
