# Architecture

A LEO satellite mesh has a topology that is fully deterministic and
computable ahead of time from orbital mechanics, but a real onboard router
still can't consult a global oracle -- it has to discover and converge on
routes from local, distributed information under bounded convergence time.
See the README for the full problem statement; this document covers the
pipeline, the three result plots, and open discussion points.

## Pipeline

    config.py
      (Config: constellation size, timestep, ground stations, faults, ...)
              |
              v
    topology/orbits.py
      (deterministic satellite + ground-station positions each timestep;
       derives orbital_period_s, num_sats, num_nodes from Config)
              |
              v
    link/visibility.py
      (line-of-sight + range/elevation checks -> LinkGraph;
       numpy-vectorized `link_graph`, or the C++ port via cpp_ext --
       see "Link-graph hot path" below)
              |
              v
    routing/
      A: centralized.py    global Dijkstra, recomputed fresh every
                            step from the true graph (oracle baseline)
      B: link_state.py      per-node LSA origination + K-round flooding,
                            each node runs Dijkstra (_dijkstra.py) over
                            its own local view (realistic convergence)
              |
              v
    sim/engine.py :: run_simulation(config, router) -> SimResult
      - steps the constellation forward in time
      - rebuilds the link graph each step (applying any fault)
      - re-routes (A recomputes; B floods/re-converges)
      - forwards packets_per_step packets hop-by-hop over the current
        topology
              |
              v
    sim/metrics.py
      (per-packet + per-step aggregation: delivery_ratio, mean_latency_s,
       mean_hops, converged_step_frac, mean_rounds_to_converge, ...
       -- exact keys in SPEC.md §5.5)

## Results

### 1. Link-graph hot path (Phase 3)

See "Link-graph hot path: Python vs. C++ (Phase 3)" below.

### 2. Normal operation: delivery ratio and latency over time

`benchmarks/normal_operation.py` runs the full default constellation
(8 planes x 18 satellites) with no fault, for both A and B, and plots
per-step delivery ratio and mean latency across the whole 12,000 s run;
see `docs/normal_operation.png`. Unlike the fault-recovery benchmark
below, this deliberately keeps the SPEC default size rather than shrinking
it, since the point here is B's behaviour under the topology churn that
size produces every timestep.

Both routers deliver essentially every packet throughout the run (A:
`delivery_ratio` = 1.0000; B: 0.9999) and track closely in mean latency
(A: 0.0424 s, B: 0.0425 s), confirming B's local Dijkstra finds routes
that are nearly as good as A's global ones even without ever fully
converging. B's `converged_step_frac` is 0.0 and `mean_rounds_to_converge`
sits at the K=5 cap for essentially every step: with 144 satellites in
constant relative motion, some node's neighbour set changes on almost
every timestep, so flooding never finishes before the next graph arrives
and B is permanently mid-flood (SPEC.md §7's staleness/flapping, exactly
as intended). This shows up in the latency panel as extra high-frequency
noise and occasional spikes for B that A doesn't have -- routes computed
from a stale two-way-checked LSDB view are occasionally a hop or two
longer than the true optimum, even though they still deliver.

### 3. Fault recovery (Phase 6)

See "Fault recovery (Phase 6)" below.

## What I'd do next

Beyond the Phase-3-specific hot-path optimizations discussed below:

- **Scale.** Spatial partitioning -- bucket satellites by orbital
  plane/shell, or a k-d tree over positions -- so the link-graph
  computation and B's neighbour discovery don't require an O(N^2) scan
  every step, combined with the SIMD/OpenMP ideas already noted below.
- **Realism.** Real orbital mechanics (SGP4/perturbations) and Earth
  rotation, rather than the simplified circular-orbit model in
  `topology/orbits.py`.
- **Scope gaps left out deliberately (SPEC.md §1, §7).** No link
  capacity, queues, or congestion, so delivery ratio here reflects
  routing and coverage only; snapshot forwarding, so a packet's whole
  path is walked over one timestep's graph and ignores topology changes
  while it's "in flight"; LSA latencies freeze at origination and go
  stale between neighbour-set changes; flapping, where a topology change
  before flooding finishes makes carried-over LSAs race newer ones; no
  laser pointing/acquisition delay or per-satellite terminal limits; no
  ground-to-ground links or ground-station transit relaying; no handover
  signalling.
- **Validation.** Compare B's link-state design and its measured
  convergence behaviour against real published LEO inter-satellite-link
  routing schemes, rather than only against the in-repo centralized
  oracle.

## Link-graph hot path: Python vs. C++ (Phase 3)

`benchmarks/benchmark_hotpath.py` times all three `link_graph` implementations
at 16/56/106/206/506 nodes (10/50/100/200/500 satellites plus 6 ground
stations); see `benchmarks/results.csv` and `docs/benchmark_hotpath.png`. At
506 nodes the median times are naive ≈ 239 ms, numpy-vectorized ≈ 27 ms, C++
≈ 1.5 ms -- roughly 9x and 160x faster than vectorized and naive respectively,
and the gap widens with N since all three are O(N²).

- **Interpreter overhead.** `link_graph_naive` calls `has_line_of_sight`,
  `in_range`, and `elevation_deg` once per pair, each of which boxes its
  arguments into small numpy arrays and pays CPython's per-call bytecode
  dispatch and object-allocation overhead. That fixed per-pair cost, not the
  arithmetic itself, is what dominates its runtime and is why it scales worst.
- **What vectorization buys.** `link_graph` replaces the O(N²) Python loop
  with a handful of O(N²) numpy ufunc/`einsum` calls, so the pairwise
  arithmetic runs as compiled, amortized-dispatch loops instead of one
  Python call per pair. The cost is allocating several O(N²) and O(N²x3)
  temporary arrays (`diff`, `dist`, `s`, `closest`, `elevation`, ...) up
  front, which is memory traffic rather than compute.
- **Memory layout.** The C++ extension never materializes those
  intermediates: each pair's scalars live in registers for the duration of
  one loop iteration, and only the final `(V,V)` distance matrix is
  allocated. Less memory traffic and better cache locality account for most
  of the additional 9x over the already-vectorized numpy version, at the
  cost of losing numpy's ability to dispatch to a multi-threaded/SIMD BLAS
  backend for free.
- **What I'd do next.** The C++ loop is still a plain scalar O(N²) scan; two
  independent next steps: (1) spatial partitioning -- bucket satellites by
  orbital plane/shell (or a k-d tree over positions) to prune pairs that
  cannot possibly be within `max_isl_range_km` or in view, turning the
  sat-sat check closer to O(N·k); (2) explicit SIMD (e.g. hand-vectorized
  AVX2 over a structure-of-arrays position layout) or OpenMP row
  parallelism over the outer loop, since each row `i` is independent.
  Neither was needed to hit the correctness/benchmark goals of this phase.

## Fault recovery (Phase 6)

`benchmarks/fault_recovery.py` kills one satellite and, separately, one
ground station partway through a run and plots per-step delivery ratio
from 600s before to 1200s after the fault for both A (centralized) and B
(link-state); see `docs/fault_recovery.png`. It uses a smaller constellation
(4 planes x 6 satellites) than the SPEC default: with the full 144-satellite
constellation, inter-satellite links appear and disappear every single
timestep as satellites move, so B's link-state database never settles even
without a fault (SPEC.md §7's flapping/staleness) and any fault-specific
signal is lost in that background churn. At this smaller size, delivery
ratio is still dominated by orbital geometry -- ground stations only see a
satellite intermittently, producing the periodic plateaus/troughs visible
on both sides of the fault -- but A's centralized rerouting recovers as
soon as another satellite comes into view, while B's `rounds_since_change`
spikes above its pre-fault baseline right after the fault as the affected
node's neighbours re-originate and reflood their LSAs.
