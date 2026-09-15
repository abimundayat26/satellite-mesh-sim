# Satellite Mesh Routing Simulator — Specification

This is the build contract for every phase in `PROJECT_PLAN.md`. It gives scope, units, data structures, interfaces and acceptance criteria. It contains no implementation code: signatures and rules only.

## 0. Key decisions and why

| Decision | Why (measured on the default constellation) |
|---|---|
| `max_isl_range_km` 2000 → **5000** | Neighbouring satellites in the same plane (18 per plane) are 2,403.6 km apart, so 2,000 km left no in-plane links. Earth blocks line of sight beyond 5,407.6 km anyway. |
| `min_elevation_deg` 25 → **10** | At 25° each ground station sees about 0.78 satellites on average; at 10° it's about 2.4 in theory and 3.3 when simulated. |
| Phase offset between planes `phasing_f` = **1** | With F=0 satellites in different planes collide (minimum distance 0.0 km); with F=1 they stay at least 128.6 km apart. |
| Traffic is **ground station ↔ ground station** only | Users sit on the ground and satellites only relay. |
| Approach B **keeps its link-state database** between timesteps; unfinished flooding carries over | Out-of-date routes and flapping then happen naturally, and those are what the project measures. |
| **No limit** on inter-satellite links per satellite (links follow visibility alone) | Simplest to define, and keeps the C++ port a genuine all-pairs O(N²) job. Mean links per satellite is about 19 and the satellite graph is connected. |

With these defaults one orbit takes 5,730.1 s, so the 12,000 s run covers about 2.09 orbits.

## 1. Scope

**In scope**
- Circular Walker-delta constellation, no perturbations, non-rotating Earth.
- Visibility-based link graph per timestep: sat–sat links (line of sight + range) and sat–ground links (elevation).
- Three link-graph implementations: naive Python, numpy (the reference), C++/pybind11. Tested for identical output, then benchmarked.
- Two routing approaches with the same interface: A, centralized Dijkstra; B, distributed link-state flooding limited to K rounds per timestep.
- Timestep simulation engine with ground station ↔ ground station traffic, per-packet outcomes and aggregate metrics.
- Permanent single-node failure (satellite or ground station) at a set time.
- pytest suite, benchmark plot, fault-recovery plot, docs.

**Out of scope** (mention only in "what I'd do next")
SGP4/perturbations; Earth rotation; atmosphere, weather or rain fade; link capacity, queues and congestion; packets in flight across timestep boundaries; laser pointing and acquisition delay; limits on laser terminals per satellite; ground-to-ground terrestrial links; ground stations relaying transit traffic; handover signalling; spatial partitioning and SIMD (discussed, not built).

## 2. Conventions and units

| Quantity | Unit | Notes |
|---|---|---|
| Distance / position | km | `float64` |
| Time | s | Simulation time `t_s`, starts at 0 |
| Latency | s | Plots may show ms |
| Angles in config | degrees | Converted to radians inside functions only |
| Earth radius `EARTH_RADIUS_KM` | 6371.0 km | Defined once in `config.py` and imported everywhere |
| Earth's gravitational parameter `MU_KM3_S2` | 398600.4418 km³/s² | Defined once in `config.py` |
| Speed of light `C_KM_S` | 299792.458 km/s | Defined once in `config.py` |

- **Frame:** Earth-centred, non-rotating, right-handed, origin at Earth's centre. +z points to the north pole; +x points to latitude 0°, longitude 0°. Ground stations are fixed in this frame.
- **Node IDs:** satellites `0 … S-1` with `id = p*M + i` (plane `p`, slot `i`), then ground stations `S … S+G-1` in config order. Here `S = N*M` and `V = S+G`.
- **Threshold comparisons are inclusive:** `distance <= range`, `closest_approach >= R_earth`, `elevation >= min_el`.
- **Float tolerances:** positions `atol=1e-6 km`; latencies `atol=1e-12 s`; cross-implementation distances `rtol=1e-12`.

## 3. Configuration (`config.py`, `Config` dataclass)

| Field | Default | Change from current code |
|---|---|---|
| `num_planes` N | 8 | — |
| `sats_per_plane` M | 18 | — |
| `altitude_km` | 550.0 | — |
| `inclination_deg` | 53.0 | — |
| `phasing_f` F | **1** | **new**: phase offset between planes |
| `ground_stations` | the 6 current (lat, lon) pairs | **fix**: set via `default_factory`, never appended in `__post_init__` |
| `max_isl_range_km` | **5000.0** | was 2000 |
| `min_elevation_deg` | **10.0** | was 25 |
| `duration_s` | 12000.0 | — |
| `timestep_s` | 10.0 | — |
| `random_seed` | 42 | — |
| `max_convergence_rounds` K | 5 | — |
| `packets_per_step` | 20 | **new** |
| `packet_ttl_hops` | 32 | **new** |
| `use_cpp` | False | **new**: use the C++ link graph in the sim |
| `fault_node_id` | None | **new** (Phase 6) |
| `fault_time_s` | None | **new** (Phase 6) |

Derived values are functions in `topology/orbits.py`, not config attributes (keeping the earlier move away from dataclass properties):
- `orbit_radius_km(config)` returns `R_earth + altitude`
- `orbital_period_s(config)` returns `2π·sqrt(r³/μ)`
- `num_sats(config)` returns `N*M`
- `num_nodes(config)` returns `S+G`

## 4. Data structures

- **Positions:** `np.ndarray`, dtype `float64`, shape `(k, 3)`, C-contiguous, km.
- **`LinkGraph`** (frozen dataclass, `link/visibility.py`)
  - `t_s: float`, `num_sats: int`
  - `distance_km: ndarray (V,V) float64`: symmetric, `np.inf` where there is no link, `np.inf` on the diagonal
  - Derived: `adjacency` (bool, `isfinite`), `latency_s` (`distance_km / C_KM_S`), `neighbors(n)` (sorted int array)
- **Next-hop table:** `ndarray (V,V) int32`
  - `nh[s,d]` is the next node on the route from `s` to `d`
  - `nh[s,s] = s`
  - `-1` means no route is known
- **`LSA`** (frozen dataclass): `origin: int`, `seq: int`, `links: tuple[tuple[int, float], ...]` of `(neighbor_id, latency_s)` sorted by neighbour.
- **`PacketStatus`** (Enum): `DELIVERED`, `DROPPED_NO_ROUTE`, `DROPPED_LINK_DOWN`, `DROPPED_TTL`.
- **`PacketRecord`** (dataclass): `packet_id`, `t_s`, `src`, `dst`, `status`, `path: tuple[int,...]`, `hops`, `latency_s` (NaN if not delivered), `optimal_latency_s` (NaN if no path exists in the true graph), `reachable: bool`, `misrouted: bool`.
- **`SimResult`** (dataclass): `metrics: dict[str, float]`, `per_step: dict[str, ndarray]` (every array has length `num_steps`, including `t_s`), `packets: list[PacketRecord]`.

## 5. Interfaces

### 5.1 Topology (`topology/orbits.py`), vectorized with no per-satellite Python loop

- `satellite_positions(t_s: float, config) -> ndarray (S,3)`
  - `u = 2πi/M + 2πF·p/(N·M) + 2π·t/T`
  - `Ω_p = 2πp/N`
  - `pos = Rz(Ω_p) · Rx(inc) · [r cos u, r sin u, 0]`
- `ground_station_positions(config) -> ndarray (G,3)`: points on the sphere of radius `R_earth`.
- `node_positions(t_s, config) -> ndarray (V,3)`: satellites first, then ground stations.

### 5.2 Link model (`link/visibility.py`)

Link rules:
- **Sat–sat:** `‖b−a‖ <= max_isl_range_km` **and** the segment's closest approach to the origin is `>= R_earth`.
  - Closest approach uses `s* = clamp(−a·(b−a)/‖b−a‖², 0, 1)`.
  - Nodes at the same position are invalid input.
- **Sat–ground:** `elevation >= min_elevation_deg`, where `sin(el) = ĝ·(s−g)/‖s−g‖`. There is no separate range limit.
- **Ground–ground:** never linked. Ground stations are endpoints only and never relay traffic.

Scalar helpers, used by tests:
- `has_line_of_sight(a, b, earth_radius_km) -> bool`
- `in_range(a, b, max_range_km) -> bool`
- `elevation_deg(ground, sat) -> float`
- `link_latency_s(a, b) -> float`

Graph builders (all return identical output):
- `link_graph_naive(positions, num_sats, config, t_s=0.0) -> LinkGraph`: loops over every pair.
- `link_graph(positions, num_sats, config, t_s=0.0) -> LinkGraph`: numpy-vectorized reference implementation.
- `link_graph_cpp(...)`: same signature, wraps the extension below.

### 5.3 C++ extension (`cpp_ext/visibility_ext.cpp`, module `visibility_ext`)

- `link_distances(positions: array_t<double> (V,3), num_sats: int, max_isl_range_km: float, min_elevation_deg: float, earth_radius_km: float) -> array_t<double> (V,V)`
- Returns the same matrix as `LinkGraph.distance_km`, with `inf` where there is no link.
- Raises `ValueError` if the input isn't shape `(V,3)` or `num_sats > V`.
- Built with CMake. Link rules and order of floating-point operations match §5.2.

### 5.4 Routing, shared interface (`routing/`)

```
class Router(Protocol):
    def update(self, graph: LinkGraph) -> None: ...
    def next_hop_table(self) -> ndarray  # (V,V) int32
    def kill(self, node_id: int) -> None: ...
```

- Edge weight is `latency_s`.
- Routes never pass through a ground station as a transit hop.
- Equal-cost ties go to the lowest predecessor ID, so results are deterministic.
- Dijkstra is written by hand with `heapq`; no scipy or networkx.

**A — `routing/centralized.py`**
- `shortest_paths(graph, source) -> (dist_s: ndarray (V,), next_hop: ndarray (V,) int32)`
- `CentralizedRouter`: on each `update`, recomputes every row from the true graph.

**B — `routing/link_state.py`, `LinkStateRouter(num_nodes, num_sats, config)`**

State per node:
- `lsdb: dict[origin → LSA]`
- `outbox: list[LSA]`, kept between timesteps
- own sequence counter
- alive flag

`update(graph)` runs these steps in order:
1. **Originate.** Each live node whose current neighbour *set* differs from the one in its last LSA (or has never sent one) creates `LSA(seq+1)` with its current latencies. It installs the LSA in its own database and adds it to its outbox.
2. **Flood for K rounds.** Rounds are synchronous: each round, every live node sends its whole outbox to every current neighbour, then clears it.
   - A receiver installs an LSA only if `seq` is newer than what it holds for that origin; it then adds the LSA to its outbox for the next round. Otherwise it drops it.
   - Anything still in an outbox after round K is sent at the next `update`, over *that* timestep's graph.
3. **Recompute routes.** Each node computes its own next-hop row with Dijkstra over its own view.
   - For its own links it uses the true current neighbours.
   - Any other link counts only if both endpoints' LSAs in its database list each other (a two-way check).

Convergence reporting:
- `converged` is True when every outbox is empty and every live node holds the latest LSA of every live node it can reach.
- `rounds_since_change` counts rounds from the last origination until convergence.
- Both are exposed through `stats() -> dict` with keys `converged`, `rounds_since_change`, `pending_lsas`.

LSA latencies are frozen when the LSA is created. Out-of-date costs are a documented limitation (§7).

### 5.5 Simulation (`sim/engine.py`, `sim/metrics.py`)

`run_simulation(config, router: Literal["centralized","link_state"] = "link_state") -> SimResult`

**Timesteps:** `t_k = k·timestep_s` for `k in range(int(duration_s // timestep_s))`.

Each timestep:
1. Compute `node_positions`.
2. Build the link graph (numpy or C++, per `use_cpp`). If a node has failed, set its row and column to `inf`.
3. Call `router.update(graph)`. If the failure fires this step, call `router.kill(id)` first.
4. Compute reference Dijkstra from every live ground station on the true graph to get `optimal_latency_s`.
5. **Generate traffic.** Draw `packets_per_step` pairs uniformly from live ground stations (`src ≠ dst`) using a single `np.random.default_rng(random_seed)`.
6. **Forward each packet.** The whole path is traversed within the current timestep's graph, since latencies are milliseconds and a timestep is 10 s. At each node `n`:
   - `n == dst` → `DELIVERED`
   - `nh == -1` → `DROPPED_NO_ROUTE`
   - no link from `n` to `nh` in the true graph → `DROPPED_LINK_DOWN`
   - hop count reaches `packet_ttl_hops` → `DROPPED_TTL`
   - Latency is the sum of true link latencies along the path.
7. **Classify.**
   - `reachable` = the true graph has a path from src to dst.
   - `misrouted` = `reachable` and (not delivered, or `latency_s > optimal_latency_s + 1e-12`).

**Metrics keys (exact):**
- `packets_sent`, `packets_delivered`
- `delivery_ratio` (delivered / sent)
- `delivery_ratio_reachable` (delivered / reachable)
- `mean_latency_s`, `mean_hops` (both over delivered packets)
- `misrouted_frac` (misrouted / reachable)
- `unreachable_frac`
- `route_divergence_frac`: mean over steps of the fraction of ordered ground-station pairs whose B-walked route is non-optimal or fails
- `converged_step_frac`, `mean_rounds_to_converge` (both NaN for centralized)

`per_step` holds the same quantities per step.

**Fault (Phase 6):** if `fault_node_id` is set, the node is dead from the first step with `t_s >= fault_time_s` until the run ends. Ground-station traffic avoids dead ground stations.

### 5.6 Benchmark (`benchmarks/benchmark_hotpath.py`)

- `run_benchmark(sizes=((2,5),(5,10),(10,10),(10,20),(20,25))) -> list[dict]`: (planes, sats per plane) = 10/50/100/200/500 satellites, 6 ground stations each.
- Timing: 1 warm-up run, then the median of 5 runs with `time.perf_counter`. Naive is skipped for a size if a single run takes more than 60 s.
- Writes `benchmarks/results.csv` (columns `n_sats, impl, median_s`) and `docs/benchmark_hotpath.png` (log–log).

## 6. Acceptance criteria

### Phase 0 — config
- `Config()` twice → each has exactly 6 ground stations.
- `Config(ground_stations=[(0,0)])` → exactly 1.
- Constants are defined only in `config.py`.

### Phase 1 — `tests/test_topology.py`
- Satellite 0 at t=0 is `(r, 0, 0)` (atol 1e-6 km).
- At least one satellite with `p > 0` and `i > 0` matches values worked out by hand; the working is shown in a test comment.
- `satellite_positions(T)` equals `satellite_positions(0)` (atol 1e-6 km).
- Every satellite is at radius `r` and every ground station at `R_earth` (rtol 1e-12). Shapes and dtypes match §4.
- Minimum satellite-to-satellite distance over one orbit at 30 s steps is `> 100 km` (measured 128.6 km).
- Code review: no Python loop over satellites.

### Phase 2 — `tests/test_link.py`
- **Earth blocks:** `(r,0,0)` and `(−r,0,0)` with range 1e9 → no link.
- **Link appears:** `(r,0,0)` and `(r cos10°, r sin10°, 0)` → link, with `latency_s == distance/C` (atol 1e-12).
- **Range boundary:** `(7000,0,0)` and `(7000,5000,0)` with range 5000.0 → link; with range 4999.999 → no link.
- **Grazing boundary:** `(R,−3000,0)` and `(R,3000,0)` → link (closest approach exactly R); at x = `R−1e-6` → no link.
- **Elevation:** ground station at `(R,0,0)`, satellite straight overhead → link. Satellites at `min_el ± 0.01°` → link / no link respectively.
- **Graph properties:** ground–ground never linked; matrix symmetric; diagonal `inf`.
- `link_graph_naive` == `link_graph` on the default config at t = 0 and t = 1000.
- **Default-config sanity** at t ∈ {0, 1000, 2500, 4000}: satellite subgraph connected; mean inter-satellite links per satellite in [15, 25] (measured ~19); mean satellites visible per ground station in [2, 5] (measured ~3.3).

### Phase 3 — `tests/test_cpp_parity.py` (use `importorskip` when the extension isn't built)
- **Default config, 10 timesteps spread over one orbit, plus every benchmark size at t=0:**
  - `isfinite` masks are exactly equal.
  - Finite distances match to `rtol=1e-12`.
- A wrong-shape input raises `ValueError`.
- **Deliverables:** `results.csv`, the plot, and a paragraph in `docs/architecture.md` explaining the measured ordering. Cover interpreter overhead, what vectorization buys, memory layout, and next steps (spatial partitioning, SIMD). No speed-up factor is required.

### Phase 4 — `tests/test_routing.py`
**Fixed graph:** 5 nodes, all satellites. Latencies in ms: 0–1:1, 1–2:1, 0–2:3, 2–3:1, 1–3:4, 3–4:2. Every shortest path is unique.
- From node 0: next hop is 1 for every destination; distances are [0, 1, 2, 3, 5] ms.
- A's full next-hop table matches the hand-computed table.
- **B converges:** with K = 4 (the graph's diameter in hops), one `update` gives a table identical to A's and `converged=True`.
- **Convergence limited by K:** with K=1, the first `update` has `converged=False`. Repeated `update`s on the same graph reach `converged=True` and a table identical to A's.
- **Link failure:** remove 1–2.
  - With K=1, the first update leaves at least one row different from A on the new graph.
  - After convergence, B matches A.
- **Ground-station transit:** a ground station that would give a cheaper path is never used as a transit hop, in A or B.
- **Dijkstra vs brute force:** on 20 seeded random connected graphs with 20 nodes, A's path costs match Floyd–Warshall (atol 1e-12).

### Phase 5 — `tests/test_sim.py`
Short config: `duration_s=600`.
- `SimResult` has every metric key from §5.5; ratios lie in [0, 1]; every `per_step` array has the step count as its length.
- Same seed → identical `metrics`; a different seed → different packet (src, dst) sequence.
- Centralized: `misrouted_frac == 0.0` and `delivery_ratio_reachable == 1.0`.
- Every delivered packet has `hops >= 2`, `latency_s >= optimal_latency_s − 1e-12`, and `mean_latency_s` in [0.002, 0.2] s.
- **Soft target (not a test):** a full default run (1,200 steps, link_state, numpy) finishes in under 5 minutes.

### Phase 6 — faults
- **Test:** satellite failure at t=300 in the short config.
  - From then on, no packet path contains the dead node, and its graph row and column are `inf`.
  - Centralized keeps `delivery_ratio_reachable == 1.0`.
- **Deliverable:** `docs/fault_recovery.png` showing per-step delivery ratio from `t_fail − 600 s` to `t_fail + 1200 s` for A and B, one satellite failure and one ground-station failure, and reconvergence rounds reported for B.

### Phase 7 — regression
- **Regression test:** seed 42, `duration_s=1200`.
  - Asserts `delivery_ratio`, `mean_latency_s`, `mean_hops` and `misrouted_frac` stay within ranges set from the first correct run (±10% relative, or ±0.02 absolute for ratios).
  - The baseline values are recorded in a test comment.
- The whole `pytest` suite runs in under 60 s.

### Phase 8 — docs
- README: problem statement and how to run.
- `docs/architecture.md`: the diagram, the three result plots, and a "what I'd do next" section.

## 7. Known limitations and discussion points

- LSA latencies go stale between neighbour-set changes, so B can be slightly non-optimal even when converged.
- Snapshot forwarding ignores topology changes while a packet is in flight.
- Flapping: when the topology changes again before flooding finishes, carried-over outbox LSAs race newer ones. Sequence numbers prevent regression, but routes can still be non-optimal.
- No link capacity or congestion, so delivery ratio reflects routing and coverage only.
