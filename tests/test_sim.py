"""
Phase 5 (SPEC.md §5.5, §6) and Phase 7 regression tests.
"""
import dataclasses

import numpy as np

from config import Config
from sim.engine import run_simulation
from sim.metrics import PacketStatus

METRIC_KEYS = {
    "packets_sent",
    "packets_delivered",
    "delivery_ratio",
    "delivery_ratio_reachable",
    "mean_latency_s",
    "mean_hops",
    "misrouted_frac",
    "unreachable_frac",
    "route_divergence_frac",
    "converged_step_frac",
    "mean_rounds_to_converge",
}

RATIO_KEYS = {
    "delivery_ratio",
    "delivery_ratio_reachable",
    "misrouted_frac",
    "unreachable_frac",
    "route_divergence_frac",
    "converged_step_frac",
}


def _short_config(**overrides):
    # Small constellation to keep the suite fast; short duration per SPEC's
    # Phase 5 acceptance criteria ("Short config: duration_s=600").
    defaults = dict(
        num_planes=4,
        sats_per_plane=6,
        duration_s=600.0,
        timestep_s=10.0,
        packets_per_step=20,
    )
    defaults.update(overrides)
    return Config(**defaults)


def test_sim_result_has_all_metric_keys_and_valid_ratios():
    result = run_simulation(_short_config(), router="link_state")
    assert METRIC_KEYS <= set(result.metrics.keys())

    num_steps = int(600.0 // 10.0)
    for key, arr in result.per_step.items():
        assert len(arr) == num_steps, f"per_step[{key!r}] has wrong length"

    for key in RATIO_KEYS:
        val = result.metrics[key]
        if not np.isnan(val):
            assert 0.0 <= val <= 1.0, f"{key}={val} out of [0, 1]"


def test_same_seed_gives_identical_metrics():
    cfg = _short_config(random_seed=7)
    r1 = run_simulation(cfg, router="link_state")
    r2 = run_simulation(cfg, router="link_state")
    assert r1.metrics == r2.metrics


def test_different_seed_gives_different_packet_sequence():
    cfg_a = _short_config(random_seed=1)
    cfg_b = _short_config(random_seed=2)
    r1 = run_simulation(cfg_a, router="link_state")
    r2 = run_simulation(cfg_b, router="link_state")
    seq1 = [(p.src, p.dst) for p in r1.packets]
    seq2 = [(p.src, p.dst) for p in r2.packets]
    assert seq1 != seq2


def test_centralized_has_perfect_routing():
    result = run_simulation(_short_config(), router="centralized")
    assert result.metrics["misrouted_frac"] == 0.0
    assert result.metrics["delivery_ratio_reachable"] == 1.0
    assert np.isnan(result.metrics["converged_step_frac"])
    assert np.isnan(result.metrics["mean_rounds_to_converge"])


def test_delivered_packets_are_physically_sane():
    result = run_simulation(_short_config(), router="centralized")
    delivered = [p for p in result.packets if p.status is PacketStatus.DELIVERED]
    assert delivered, "expected at least one delivered packet"
    for p in delivered:
        assert p.hops >= 2
        assert p.latency_s >= p.optimal_latency_s - 1e-12

    mean_latency_s = result.metrics["mean_latency_s"]
    assert 0.002 <= mean_latency_s <= 0.2


def test_link_state_runs_without_error():
    result = run_simulation(_short_config(), router="link_state")
    assert result.metrics["packets_sent"] > 0


# --- Phase 7 regression test -------------------------------------------
# Baseline recorded from a known-good run of
# `run_simulation(Config(duration_s=1200.0), "link_state")` (seed 42, default
# constellation):
#   delivery_ratio  = 0.99875
#   mean_latency_s  = 0.04286071753260577
#   mean_hops       = 4.824780976220275
#   misrouted_frac  = 0.45125
def test_short_run_metrics_within_expected_range():
    cfg = Config(duration_s=1200.0)
    result = run_simulation(cfg, router="link_state")

    assert abs(result.metrics["delivery_ratio"] - 0.99875) <= 0.02
    assert abs(result.metrics["misrouted_frac"] - 0.45125) <= 0.02

    baseline_mean_latency_s = 0.04286071753260577
    assert abs(result.metrics["mean_latency_s"] - baseline_mean_latency_s) <= 0.1 * baseline_mean_latency_s

    baseline_mean_hops = 4.824780976220275
    assert abs(result.metrics["mean_hops"] - baseline_mean_hops) <= 0.1 * baseline_mean_hops
