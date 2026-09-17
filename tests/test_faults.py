"""
Phase 6 fault-injection acceptance tests. See SPEC.md §6 "Phase 6 — faults".

The fault-injection mechanics themselves live in sim/engine.py (already
implemented as part of Phase 5): a dead node's graph row/column go to inf
from fault_time_s onward, and traffic never originates/terminates at a dead
ground station. These tests only verify that observable contract.
"""
from config import Config
from sim.engine import run_simulation
from topology.orbits import num_sats


def _short_config(**overrides):
    defaults = dict(
        num_planes=4,
        sats_per_plane=6,
        duration_s=600.0,
        timestep_s=10.0,
        packets_per_step=20,
    )
    defaults.update(overrides)
    return Config(**defaults)


def test_satellite_fault_removes_node_from_all_paths():
    cfg = _short_config(fault_node_id=0, fault_time_s=300.0)
    result = run_simulation(cfg, router="centralized")

    post_fault = [p for p in result.packets if p.t_s >= 300.0]
    assert post_fault, "expected packets after the fault fires"
    for p in post_fault:
        assert 0 not in p.path

    assert result.metrics["delivery_ratio_reachable"] == 1.0


def test_ground_station_fault_excludes_it_from_traffic():
    cfg = _short_config()
    ground_id = num_sats(cfg)
    cfg = _short_config(fault_node_id=ground_id, fault_time_s=300.0)
    result = run_simulation(cfg, router="centralized")

    post_fault = [p for p in result.packets if p.t_s >= 300.0]
    assert post_fault, "expected packets after the fault fires"
    for p in post_fault:
        assert p.src != ground_id
        assert p.dst != ground_id
        assert ground_id not in p.path

    assert result.metrics["delivery_ratio_reachable"] == 1.0
