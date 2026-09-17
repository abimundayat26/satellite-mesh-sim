"""
Phase 6 deliverable: per-step delivery-ratio recovery around a single-node
failure, for both routing approaches. Produces docs/fault_recovery.png.
See SPEC.md §6 "Phase 6 -- faults".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import Config
from sim.engine import run_simulation
from topology.orbits import num_sats

FAULT_TIME_S = 900.0
DURATION_S = 2200.0
WINDOW_BEFORE_S = 600.0
WINDOW_AFTER_S = 1200.0

PLOT_PATH = "docs/fault_recovery.png"

FAULT_KINDS = ("satellite", "ground_station")
ROUTERS = ("centralized", "link_state")

# A smaller constellation than the SPEC default: with 8x18=144 satellites the
# topology churns every single timestep (links appear/disappear continuously
# as satellites move), which drowns out any fault-specific convergence signal
# in background flapping (SPEC.md §7). This size still shows the same
# fault/routing behaviour while keeping runtime and the plot readable.
BASE_CONFIG_KWARGS = dict(num_planes=4, sats_per_plane=6, packets_per_step=200)


def _fault_node_id(kind: str, config: Config) -> int:
    if kind == "satellite":
        return 0
    return num_sats(config)


def run_fault_recovery():
    """Run every (fault_kind, router) combination and collect per-step data."""
    data = {}
    for kind in FAULT_KINDS:
        base_config = Config(**BASE_CONFIG_KWARGS)
        node_id = _fault_node_id(kind, base_config)
        for router in ROUTERS:
            cfg = Config(
                **BASE_CONFIG_KWARGS,
                fault_node_id=node_id,
                fault_time_s=FAULT_TIME_S,
                duration_s=DURATION_S,
            )
            result = run_simulation(cfg, router=router)
            data[(kind, router)] = result.per_step
            print(f"fault={kind:14s} router={router:12s} node_id={node_id}")

    return data


RECONVERGENCE_PEAK_WINDOW_S = 120.0


def _reconvergence_rounds(per_step) -> tuple:
    """Baseline vs. fault-induced peak of B's rounds_since_change.

    The default constellation's topology churns every timestep as
    satellites move, so LinkStateRouter (SPEC.md §7: staleness/flapping
    are intended) rarely reports converged=True even without a fault --
    "time to full convergence" isn't a meaningful number here. Instead we
    compare the background rounds_since_change (averaged over the window
    just before the fault) to its peak just after the fault, which
    isolates the extra convergence work the fault itself causes.
    """
    t_s = per_step["t_s"]
    rounds = per_step["rounds_to_converge"]

    pre_mask = (t_s >= FAULT_TIME_S - WINDOW_BEFORE_S) & (t_s < FAULT_TIME_S)
    post_mask = (t_s >= FAULT_TIME_S) & (t_s < FAULT_TIME_S + RECONVERGENCE_PEAK_WINDOW_S)

    baseline = float(np.nanmean(rounds[pre_mask])) if pre_mask.any() else float("nan")
    peak = float(np.nanmax(rounds[post_mask])) if post_mask.any() else float("nan")
    return baseline, peak


def plot_fault_recovery(data, path=PLOT_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, len(FAULT_KINDS), figsize=(12, 5), sharey=True)

    for ax, kind in zip(axes, FAULT_KINDS):
        for router in ROUTERS:
            per_step = data[(kind, router)]
            rel_t = per_step["t_s"] - FAULT_TIME_S
            mask = (rel_t >= -WINDOW_BEFORE_S) & (rel_t <= WINDOW_AFTER_S)
            label = "A (centralized)" if router == "centralized" else "B (link-state)"
            ax.plot(rel_t[mask], per_step["delivery_ratio"][mask], marker=".", label=label)

        ax.axvline(0.0, color="black", linestyle="--", linewidth=1, label="fault")

        baseline, peak = _reconvergence_rounds(data[(kind, "link_state")])
        if np.isfinite(baseline) and np.isfinite(peak):
            ax.text(
                0.02,
                0.03,
                f"B rounds-since-change: baseline {baseline:.0f} -> peak {peak:.0f}",
                transform=ax.transAxes,
                fontsize=9,
            )

        title = "Satellite failure" if kind == "satellite" else "Ground-station failure"
        ax.set_title(title)
        ax.set_xlabel("Time since fault (s)")
        ax.grid(True, linestyle=":", alpha=0.5)

    axes[0].set_ylabel("Delivery ratio")
    axes[0].legend(loc="lower right", fontsize=8)
    fig.suptitle("Delivery-ratio recovery around a single-node failure")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    data = run_fault_recovery()
    plot_fault_recovery(data)
    for kind in FAULT_KINDS:
        baseline, peak = _reconvergence_rounds(data[(kind, "link_state")])
        print(
            f"{kind}: B rounds_since_change baseline={baseline:.0f} "
            f"peak_after_fault={peak:.0f}"
        )
    print(f"wrote {PLOT_PATH}")
