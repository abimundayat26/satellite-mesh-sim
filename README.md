# Satellite Mesh Routing Simulator

Simplified LEO constellation network simulator: time-varying topology,
distributed link-state routing vs. a centralized baseline, a C++-ported
hot path, and fault injection.

See `docs/architecture.md` for the full write-up (fill in as you build)
and the project outline doc for the phase-by-phase plan.

## Setup

    pip install -r requirements.txt
    # build the C++ extension (Phase 3)
    cd cpp_ext && cmake -B build && cmake --build build

## Run tests

    pytest tests/
