# Satellite Mesh Routing Simulator

Terrestrial network routing (BGP, OSPF, ...) reacts to topology it cannot
predict in advance: links fail, traffic shifts, peers appear. A LEO
satellite mesh is different — the topology is fully deterministic and
computable ahead of time from orbital mechanics — yet a real satellite's
onboard router can't just consult a global oracle; it still has to
discover and converge on routes from local, distributed information,
bounded by real convergence time. This project simulates a time-varying
LEO constellation and compares two routers built against that same
known-topology-but-locally-unknown setup: **A**, a centralized baseline
with instantaneous global knowledge (an oracle / upper bound), and **B**,
a distributed link-state router with realistic flooding and convergence
delay — to measure the practical routing cost when a network's future is
knowable in principle but must still be learned in practice.

See `docs/architecture.md` for the architecture diagram, results, and
discussion, and `PROJECT_PLAN.md` for the phase-by-phase build log.

## Setup

    pip install -r requirements.txt
    # build the C++ extension (Phase 3; optional -- Config.use_cpp is False by default)
    cd cpp_ext && cmake -B build && cmake --build build

## How to run

### Run the simulator programmatically

    from config import Config
    from sim.engine import run_simulation

    result = run_simulation(Config(), router="link_state")  # or "centralized"
    print(result.metrics)

`result.metrics` holds the summary metrics defined in SPEC.md §5.5
(`delivery_ratio`, `mean_latency_s`, `converged_step_frac`, ...);
`result.per_step` holds the same quantities broken out per timestep, and
`result.packets` holds the full per-packet log.

### Run tests

    pytest tests/

### Regenerate the result plots

    python benchmarks/benchmark_hotpath.py   # docs/benchmark_hotpath.png, benchmarks/results.csv
    python benchmarks/normal_operation.py    # docs/normal_operation.png
    python benchmarks/fault_recovery.py      # docs/fault_recovery.png
