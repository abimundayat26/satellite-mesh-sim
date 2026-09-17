# Architecture

## Pipeline

    config.py
      (Config: constellation size, timestep, ground stations, faults, ...)
              |
              v
    topology/orbits.py
      (deterministic satellite + ground-station positions each timestep)
              |
              v
    link/visibility.py
      (line-of-sight + range/elevation checks -> LinkGraph;
       numpy-vectorized, or the C++ port via cpp_ext)
              |
              v
    routing/
      A: centralized.py    global Dijkstra, recomputed every step (oracle)
      B: link_state.py     per-node LSA flooding + local Dijkstra
              |
              v
    sim/engine.py :: run_simulation(config, router) -> SimResult
      - steps time, rebuilds the graph, re-routes, forwards packets
              |
              v
    sim/metrics.py
      (delivery_ratio, mean_latency_s, converged_step_frac, ...)

## Results

### 1. Link-graph hot path (Phase 3)

`benchmarks/benchmark_hotpath.py` times naive Python, numpy, and C++ at
16-506 nodes; see `docs/benchmark_hotpath.png`. At 506 nodes: naive ~239ms,
numpy ~27ms, C++ ~1.5ms -- ~9x and ~160x faster respectively, gap widens
with N since all three are O(N²).

- **Naive Python** pays CPython call/dispatch overhead per pair, not
  arithmetic cost -- that's why it scales worst.
- **Numpy** trades the per-pair Python calls for a handful of O(N²)
  vectorized ops, at the cost of several O(N²) temporary arrays.
- **C++** never materializes those temporaries -- each pair's scalars
  stay in registers, so it wins mostly on memory traffic and cache
  locality (at the cost of losing numpy's BLAS dispatch).
- **Next step:** spatial partitioning (bucket by plane/shell, or a k-d
  tree) to prune pairs, plus SIMD/OpenMP over the still-scalar C++ loop.

### 2. Normal operation: delivery ratio and latency over time

`benchmarks/normal_operation.py` runs the full default constellation with
no fault, for both routers; see `docs/normal_operation.png`.

Both deliver ~100% of packets (A: 1.0000, B: 0.9999) with close mean
latency (A: 0.0424s, B: 0.0425s). B's `converged_step_frac` is 0.0 and
`mean_rounds_to_converge` sits at the K=5 cap almost every step -- with
144 satellites in motion, some neighbor set changes nearly every timestep,
so B is permanently mid-flood. That shows up as extra latency noise for B,
not lost packets.

### 3. Fault recovery (Phase 6)

`benchmarks/fault_recovery.py` kills a satellite, then separately a
ground station, and plots delivery ratio around the fault for both
routers; see `docs/fault_recovery.png`. Uses a smaller constellation
(4 planes x 6 sats) so the fault's signal isn't buried in background
topology churn. A reroutes as soon as another satellite is visible; B's
`rounds_since_change` spikes above baseline right after the fault as
neighbors re-originate and reflood LSAs.

## What I'd do next

- Spatial partitioning + SIMD/OpenMP for the hot path (see above).
- Real orbital mechanics (SGP4, Earth rotation) instead of circular orbits.
- Out of scope by design: link capacity/congestion, packets in flight
  across timestep boundaries, laser pointing/acquisition delay, ground-
  station transit relaying, handover signalling.
- Compare B's convergence behavior against published LEO ISL routing
  schemes instead of only the in-repo oracle.
