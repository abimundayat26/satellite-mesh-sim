# Satellite Mesh Routing Simulator — Project Outline

**Goal:** simulate LEO satellite mesh routing end to end -- topology, link model, two routing strategies, a C++ hot-path port, and fault injection.
**Stack:** Python 3 + numpy + matplotlib + pytest; one C++17 + pybind11 extension for the hot path; CMake.

---

## Phase 0 — Setup & Scoping (0.5-1h)
- [ ] Repo skeleton: `topology/`, `link/`, `routing/`, `sim/`, `cpp_ext/`, `tests/`, `docs/`
- [ ] Pick constants up front and write them down: number of orbital planes, satellites per plane, altitude, number of ground stations, sim duration, timestep size, ISL max range, min elevation angle for sat-ground links
- [ ] Fix a random seed for anything stochastic (traffic generation, fault injection) — reproducibility matters for your test suite later
- [ ] README stub with problem statement (fill in fully in Phase 8)

**Done when:** you can describe the constellation in one paragraph and everyone downstream (link model, routing) can consume a shared config.

---

## Phase 1 — Topology Model (3-4h)
- [ ] Simplified orbit model: circular orbits, constant angular velocity, N planes × M satellites (Walker-style), evenly phased. Skip SGP4/perturbations entirely.
- [ ] Position function: given time `t`, return 3D position of every satellite (and fixed lat/lon for ground stations — treat Earth as non-rotating to save time unless you want the extra realism)
- [ ] Vectorize this with numpy from the start (array of positions per timestep), not a Python loop per satellite — sets you up cleanly for Phase 3

**Tests**
- [ ] Position at `t=0` matches hand-computed values for at least one satellite
- [ ] Position at `t=T` (one orbital period) equals position at `t=0` within floating-point tolerance

**Done when:** you can call `positions(t)` and get back every node's location for any `t`.

---

## Phase 2 — Link / Visibility Model (2-3h)
- [ ] Pairwise visibility check per timestep: line-of-sight not blocked by Earth (geometric check — does the segment between two nodes pass within Earth's radius of Earth's center) + within max range
- [ ] Sat-ground links: additionally check minimum elevation angle
- [ ] Compute link latency from distance (distance / speed of light)
- [ ] Output: adjacency structure (matrix or edge list) per timestep — this is the graph the routing layer will consume

**Tests**
- [ ] Hand-built 3-node case: two satellites with Earth between them → no link; move them to the same side → link appears
- [ ] Boundary cases: exactly at max range, exactly grazing Earth's limb

**Done when:** `link_graph(t)` returns a correct adjacency structure, verified against hand-built cases.

**Note:** this all-pairs check is your O(N²)-per-timestep hot path — this is what gets ported in Phase 3.

---

## Phase 3 — C++ Hot-Path Port (3-4h)
- [ ] Write a small pybind11 extension that takes the position array for time `t` and returns the same adjacency structure as your Python `link_graph(t)`
- [ ] Build it (CMake or `setup.py` + pybind11) as an importable Python module
- [ ] **Correctness first:** unit test that the C++ output matches the Python output exactly (or within float tolerance) on identical inputs, across several timesteps
- [ ] **Benchmark second:** wall-clock time, pure Python (both a naive loop version and your numpy-vectorized version) vs. the C++ extension, across increasing N (e.g. 10 / 50 / 100 / 200 / 500 satellites). Plot it.
- [ ] Write up *why*: interpreter overhead per pair-check in the naive loop, what numpy vectorization buys you, and what the C++ version does differently (no per-element Python object overhead, tighter memory layout). Note what you'd do next for further speedup (spatial partitioning to avoid O(N²) altogether, SIMD) even if you don't implement it.

**Done when:** you have a correctness test proving parity, a benchmark plot, and a paragraph explaining the result — not just a faster function.

---

## Phase 4 — Routing Layer (4-5h)
This is where the "real" comparison lives — make it a genuine contrast, not two versions of the same thing:

- **Approach A — centralized/reactive baseline:** every timestep, recompute global shortest paths (Dijkstra) using complete topology knowledge. Unrealistic (no real network has instant global knowledge) but gives you an upper bound.
- **Approach B — distributed link-state:** each node only knows its direct neighbors' link state at first. Nodes exchange routing info with neighbors over a bounded number of "rounds" per topology change before you lock in that timestep's routing decision. Packets can be misrouted while convergence is still in progress.
- [ ] Implement A
- [ ] Implement B, including the round-limited convergence process
- [ ] Track: how often B's decisions diverge from A's, and how long (in rounds) B takes to converge after a topology change
- [ ] Note the "flapping" problem as a discussion point even if you don't fully solve it: what happens if topology changes again before convergence finishes

**Tests**
- [ ] Small fixed (non-time-varying) topology, ~5 nodes, hand-computed shortest paths — verify both A and B converge to the correct routing table

**Done when:** both approaches run on the same topology and you can quantify the gap between them.

---

## Phase 5 — Simulation Engine & Traffic (2-3h)
- [ ] Main loop per timestep: update positions (Phase 1) → compute link graph, Python or C++ (Phase 2/3) → update routing tables (Phase 4) → inject synthetic traffic (random source/dest pairs) → route packets hop-by-hop per current table → record outcome
- [ ] Metrics per run: delivery ratio, average end-to-end latency, average hop count, fraction of packets misrouted due to stale routes
- [ ] Config knobs: satellite count, ground station count, duration, traffic rate — so you can re-run at different scales for the benchmark plots

**Done when:** one function call runs a full simulation and returns a metrics dict.

---

## Phase 6 — Fault Injection (1-2h)
- [ ] Kill a random node mid-run (satellite or ground station)
- [ ] Measure: re-convergence time (rounds/timesteps), packets dropped/misrouted during the outage, delivery ratio recovery curve
- [ ] Optional: compare satellite-failure impact vs. ground-station-failure impact

**Done when:** you have a before/during/after plot of delivery ratio around a failure event.

---

## Phase 7 — Testing & Polish (2-3h, overlaps with earlier phases but budget it explicitly)
- [ ] Consolidate all unit tests from Phases 1-4 into one suite, `pytest` runnable
- [ ] Add 1-2 regression tests: fixed seed, run a short sim, assert aggregate metrics land within an expected range — guards against future changes silently breaking things
- [ ] Optional: GitHub Actions running pytest on push — small addition, decent "real-world software practice" signal

---

## Phase 8 — Docs & Results (2-3h)
- [ ] README: problem statement (why LEO routing is a genuinely different problem from terrestrial networking — topology is deterministic and known in advance, but you still need bounded, distributed convergence), how to run it
- [ ] One architecture diagram: topology → link model (Python + C++) → routing (A vs B) → sim loop → metrics
- [ ] Results section with three artifacts: the Phase 3 benchmark plot, a normal-operation delivery/latency-over-time plot, and the Phase 6 fault-recovery plot
- [ ] Short "what I'd do next" section: spatial partitioning for scale, real orbital mechanics (SGP4), comparison to actual space-routing literature — shows you know the limits of what you built

---
