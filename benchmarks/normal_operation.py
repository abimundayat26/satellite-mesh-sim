"""
Per-step delivery ratio and latency over a full, fault-free run, for both
routing approaches. Produces docs/normal_operation.png. Uses the full
default constellation (unlike fault_recovery.py) to show B's link-state
database under normal topology churn.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import Config
from sim.engine import run_simulation

PLOT_PATH = "docs/normal_operation.png"

ROUTERS = ("centralized", "link_state")


def run_normal_operation():
    """Run both routers on the default (fault-free) config and collect
    per-step data and summary metrics."""
    data = {}
    metrics = {}
    for router in ROUTERS:
        result = run_simulation(Config(), router=router)
        data[router] = result.per_step
        metrics[router] = result.metrics
        print(f"router={router:12s} done")
    return data, metrics


def plot_normal_operation(data, path=PLOT_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    fig, (ax_delivery, ax_latency) = plt.subplots(1, 2, figsize=(12, 5))

    for router in ROUTERS:
        per_step = data[router]
        label = "A (centralized)" if router == "centralized" else "B (link-state)"
        ax_delivery.plot(per_step["t_s"], per_step["delivery_ratio"], label=label)
        ax_latency.plot(per_step["t_s"], per_step["mean_latency_s"], label=label)

    ax_delivery.set_title("Delivery ratio over time")
    ax_delivery.set_xlabel("Time (s)")
    ax_delivery.set_ylabel("Delivery ratio")
    ax_delivery.grid(True, linestyle=":", alpha=0.5)
    ax_delivery.legend(loc="lower right", fontsize=8)

    ax_latency.set_title("Mean latency over time")
    ax_latency.set_xlabel("Time (s)")
    ax_latency.set_ylabel("Mean latency (s)")
    ax_latency.grid(True, linestyle=":", alpha=0.5)
    ax_latency.legend(loc="upper right", fontsize=8)

    fig.suptitle("Normal operation: default constellation, no fault")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    data, metrics = run_normal_operation()
    plot_normal_operation(data)
    for router in ROUTERS:
        m = metrics[router]
        print(
            f"{router}: delivery_ratio={m['delivery_ratio']:.4f} "
            f"delivery_ratio_reachable={m['delivery_ratio_reachable']:.4f} "
            f"mean_latency_s={m['mean_latency_s']:.6f} "
            f"converged_step_frac={m['converged_step_frac']:.4f} "
            f"mean_rounds_to_converge={m['mean_rounds_to_converge']:.4f}"
        )
    print(f"wrote {PLOT_PATH}")
