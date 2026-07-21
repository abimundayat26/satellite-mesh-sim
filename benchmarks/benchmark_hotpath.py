"""
Phase 3 benchmark: pure Python (naive + numpy-vectorized) vs. the C++
extension, across increasing satellite counts. Produces the plot for
docs/architecture.md's results section.
"""


def run_benchmark(satellite_counts=(10, 50, 100, 200, 500)):
    """
    TODO: for each N, time link_graph() -- naive Python, numpy version,
    and cpp_ext.link_graph() -- and record wall-clock time. Plot with
    matplotlib.
    """
    raise NotImplementedError


if __name__ == "__main__":
    run_benchmark()
