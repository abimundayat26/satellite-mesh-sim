# Satellite Mesh Routing Simulator

A LEO constellation's topology is deterministic and known in advance, but
no satellite has a global view -- it still has to discover and converge on
routes locally. This project simulates a time-varying constellation and
compares two routers against that setup: **A**, a centralized oracle with
instant global knowledge, and **B**, a distributed link-state router with
realistic flooding and bounded convergence.

See `docs/architecture.md` for the diagram and results, `PROJECT_PLAN.md`
for the build log.

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
