"""
Prove the C++ extension matches the Python reference exactly (within
float tolerance) before trusting the benchmark numbers.
"""
import numpy as np
import pytest

visibility_ext = pytest.importorskip("visibility_ext")

from config import Config, EARTH_RADIUS_KM
from link.visibility import link_graph, link_graph_cpp
from topology.orbits import node_positions, num_sats, orbital_period_s

BENCHMARK_SIZES = ((2, 5), (5, 10), (10, 10), (10, 20), (20, 25))


def _assert_parity(py_graph, cpp_graph):
    py_finite = np.isfinite(py_graph.distance_km)
    cpp_finite = np.isfinite(cpp_graph.distance_km)
    assert np.array_equal(py_finite, cpp_finite)
    np.testing.assert_allclose(
        py_graph.distance_km[py_finite],
        cpp_graph.distance_km[py_finite],
        rtol=1e-12,
    )


@pytest.mark.parametrize("step", range(10))
def test_cpp_matches_python_default_config(step):
    config = Config()
    period = orbital_period_s(config)
    t_s = step * period / 10
    n_sats = num_sats(config)
    positions = node_positions(t_s, config)

    py_graph = link_graph(positions, n_sats, config, t_s=t_s)
    cpp_graph = link_graph_cpp(positions, n_sats, config, t_s=t_s)

    _assert_parity(py_graph, cpp_graph)


@pytest.mark.parametrize("planes,sats_per_plane", BENCHMARK_SIZES)
def test_cpp_matches_python_benchmark_sizes(planes, sats_per_plane):
    config = Config(num_planes=planes, sats_per_plane=sats_per_plane)
    n_sats = num_sats(config)
    positions = node_positions(0.0, config)

    py_graph = link_graph(positions, n_sats, config, t_s=0.0)
    cpp_graph = link_graph_cpp(positions, n_sats, config, t_s=0.0)

    _assert_parity(py_graph, cpp_graph)


def test_cpp_wrong_shape_raises_value_error():
    bad_positions = np.zeros((10, 2), dtype=np.float64)
    with pytest.raises(ValueError):
        visibility_ext.link_distances(bad_positions, 5, 5000.0, 10.0, EARTH_RADIUS_KM)


def test_cpp_num_sats_exceeds_v_raises_value_error():
    positions = np.zeros((10, 3), dtype=np.float64)
    with pytest.raises(ValueError):
        visibility_ext.link_distances(positions, 11, 5000.0, 10.0, EARTH_RADIUS_KM)
