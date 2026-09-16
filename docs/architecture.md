# Architecture

TODO (Phase 8): fill in once the pieces exist.

- Problem statement -- why LEO routing differs from terrestrial networking
- Diagram: topology -> link model (Python + C++) -> routing (A vs B) -> sim loop -> metrics
- Results: benchmark plot, normal-operation delivery/latency plot, fault-recovery plot
- What I'd do next

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
