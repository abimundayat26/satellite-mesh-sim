"""
Phase 3 benchmark: pure Python (naive + numpy-vectorized) vs. the C++
extension, across increasing satellite counts. Produces benchmarks/results.csv
and docs/benchmark_hotpath.png.
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import Config
from link.visibility import link_graph, link_graph_naive
from topology.orbits import node_positions, num_sats

try:
    from link.visibility import link_graph_cpp

    import visibility_ext  # noqa: F401  -- probe that the extension is actually built

    _CPP_AVAILABLE = True
except ImportError:
    _CPP_AVAILABLE = False

NAIVE_TIME_LIMIT_S = 60.0
N_TIMED_RUNS = 5

IMPLS = [("naive", link_graph_naive), ("vectorized", link_graph)]
if _CPP_AVAILABLE:
    IMPLS.append(("cpp", link_graph_cpp))

RESULTS_CSV = "benchmarks/results.csv"
PLOT_PATH = "docs/benchmark_hotpath.png"


def _time_one(fn, positions, n_sats, config):
    start = time.perf_counter()
    fn(positions, n_sats, config, t_s=0.0)
    return time.perf_counter() - start


def run_benchmark(sizes=((2, 5), (5, 10), (10, 10), (10, 20), (20, 25))):
    results = []

    for planes, sats_per_plane in sizes:
        config = Config(num_planes=planes, sats_per_plane=sats_per_plane)
        n_sats = num_sats(config)
        positions = node_positions(0.0, config)
        n_total = positions.shape[0]

        for name, fn in IMPLS:
            # Warm-up run also serves as the naive 60s trial-run check.
            warmup_time = _time_one(fn, positions, n_sats, config)
            if name == "naive" and warmup_time > NAIVE_TIME_LIMIT_S:
                print(f"n_sats={n_total:4d} impl={name:12s} skipped (>{NAIVE_TIME_LIMIT_S:.0f}s)")
                continue

            timings = [_time_one(fn, positions, n_sats, config) for _ in range(N_TIMED_RUNS)]
            median_s = float(np.median(timings))
            results.append({"n_sats": n_total, "impl": name, "median_s": median_s})
            print(f"n_sats={n_total:4d} impl={name:12s} median_s={median_s:.6f}")

    return results


def write_csv(results, path=RESULTS_CSV):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["n_sats", "impl", "median_s"])
        writer.writeheader()
        writer.writerows(results)


def plot_results(results, path=PLOT_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    by_impl = {}
    for row in results:
        by_impl.setdefault(row["impl"], {"n": [], "t": []})
        by_impl[row["impl"]]["n"].append(row["n_sats"])
        by_impl[row["impl"]]["t"].append(row["median_s"])

    fig, ax = plt.subplots(figsize=(7, 5))
    for impl, data in by_impl.items():
        order = np.argsort(data["n"])
        n_arr = np.array(data["n"])[order]
        t_arr = np.array(data["t"])[order]
        ax.plot(n_arr, t_arr, marker="o", label=impl)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of satellites")
    ax.set_ylabel("Median wall time (s)")
    ax.set_title("Link-graph hot path: naive vs. vectorized vs. C++")
    ax.legend()
    ax.grid(True, which="both", ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    if not _CPP_AVAILABLE:
        print("visibility_ext not built -- build cpp_ext/ first for full results")
    results = run_benchmark()
    write_csv(results)
    plot_results(results)
    print(f"wrote {RESULTS_CSV} and {PLOT_PATH}")
