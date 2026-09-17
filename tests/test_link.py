"""Phase 2 tests: hand-built visibility cases, boundary conditions, and
default-config sanity checks."""
import numpy as np
import pytest

from config import Config, EARTH_RADIUS_KM, C_KM_S
from link.visibility import (
    elevation_deg,
    has_line_of_sight,
    in_range,
    link_graph,
    link_graph_naive,
    link_latency_s,
)
from topology.orbits import node_positions, num_sats as topo_num_sats


R = EARTH_RADIUS_KM


def test_earth_blocks_line_of_sight():
    a = np.array([R, 0.0, 0.0])
    b = np.array([-R, 0.0, 0.0])
    assert not has_line_of_sight(a, b, R)
    assert in_range(a, b, 1e9)


def test_link_appears_when_unblocked():
    r = R + 550.0  # a plausible orbit radius; points on Earth's surface itself would self-occlude
    a = np.array([r, 0.0, 0.0])
    b = np.array([r * np.cos(np.radians(10.0)), r * np.sin(np.radians(10.0)), 0.0])
    assert has_line_of_sight(a, b, R)
    dist = np.linalg.norm(b - a)
    assert link_latency_s(a, b) == pytest.approx(dist / C_KM_S, abs=1e-12)


def test_boundary_at_max_range():
    a = np.array([7000.0, 0.0, 0.0])
    b = np.array([7000.0, 5000.0, 0.0])
    assert in_range(a, b, 5000.0)
    assert not in_range(a, b, 4999.999)


def test_boundary_grazing_earth_limb():
    a = np.array([R, -3000.0, 0.0])
    b = np.array([R, 3000.0, 0.0])
    assert has_line_of_sight(a, b, R)

    a2 = np.array([R - 1e-6, -3000.0, 0.0])
    b2 = np.array([R - 1e-6, 3000.0, 0.0])
    assert not has_line_of_sight(a2, b2, R)


def test_elevation_overhead_and_boundary():
    ground = np.array([R, 0.0, 0.0])
    sat_overhead = np.array([R + 550.0, 0.0, 0.0])
    assert elevation_deg(ground, sat_overhead) == pytest.approx(90.0, abs=1e-9)

    min_el = 10.0
    # Place a satellite at exactly min_el elevation, then nudge +/- 0.01 deg.
    r_orbit = R + 550.0

    def sat_at_elevation(el_deg):
        # Bisect on the central angle theta; elevation is monotonic in it.
        def el_of_theta(theta):
            sat = np.array([r_orbit * np.cos(theta), r_orbit * np.sin(theta), 0.0])
            return elevation_deg(ground, sat)

        lo, hi = 1e-6, np.pi / 2
        for _ in range(100):
            mid = (lo + hi) / 2
            if el_of_theta(mid) > el_deg:
                lo = mid
            else:
                hi = mid
        theta = (lo + hi) / 2
        return np.array([r_orbit * np.cos(theta), r_orbit * np.sin(theta), 0.0])

    sat_above = sat_at_elevation(min_el + 0.01)
    sat_below = sat_at_elevation(min_el - 0.01)
    assert elevation_deg(ground, sat_above) >= min_el
    assert elevation_deg(ground, sat_below) < min_el


def test_has_line_of_sight_raises_on_coincident_positions():
    a = np.array([R + 550.0, 0.0, 0.0])
    assert (a == a).all()
    with pytest.raises(ValueError):
        has_line_of_sight(a, a.copy(), R)


def test_elevation_deg_raises_on_coincident_positions():
    # ‖s-g‖ == 0 makes elevation undefined; must not silently divide by zero.
    same_point = np.array([R, 0.0, 0.0])
    with pytest.raises(ValueError):
        elevation_deg(same_point, same_point.copy())


def test_elevation_deg_raises_regardless_of_which_arg_is_ground_vs_sat():
    # The guard must trigger regardless of argument order.
    same_point = np.array([R + 100.0, 50.0, -20.0])
    with pytest.raises(ValueError):
        elevation_deg(same_point, same_point.copy())
    with pytest.raises(ValueError):
        elevation_deg(same_point.copy(), same_point)


def test_elevation_deg_still_correct_near_but_not_at_coincidence():
    # Only exact coincidence should raise, not a near-zero separation.
    ground = np.array([R, 0.0, 0.0])
    sat = np.array([R + 1e-6, 0.0, 0.0])  # 1 mm above the ground station
    assert elevation_deg(ground, sat) == pytest.approx(90.0, abs=1e-3)


def test_link_graph_naive_raises_on_coincident_sat_ground_pair():
    # The sat-ground branch must surface the same guard as sat-sat does.
    config = Config()
    ground = np.array([R, 0.0, 0.0])
    sat_at_ground = ground.copy()  # invalid: satellite "at" the ground station
    positions = np.vstack([sat_at_ground, ground])
    with pytest.raises(ValueError):
        link_graph_naive(positions, num_sats=1, config=config, t_s=0.0)


def test_graph_properties():
    config = Config()
    positions = node_positions(0.0, config)
    n_sats = topo_num_sats(config)
    graph = link_graph(positions, n_sats, config, t_s=0.0)

    n_ground = len(config.ground_stations)
    ground_block = graph.distance_km[n_sats:, n_sats:]
    assert np.all(np.isinf(ground_block[~np.eye(n_ground, dtype=bool)]))

    assert np.allclose(graph.distance_km, graph.distance_km.T, equal_nan=False)
    assert np.all(np.isinf(np.diag(graph.distance_km)))


@pytest.mark.parametrize("t_s", [0.0, 1000.0])
def test_naive_matches_vectorized(t_s):
    config = Config()
    positions = node_positions(t_s, config)
    n_sats = topo_num_sats(config)

    naive = link_graph_naive(positions, n_sats, config, t_s=t_s)
    vectorized = link_graph(positions, n_sats, config, t_s=t_s)

    naive_finite = np.isfinite(naive.distance_km)
    vec_finite = np.isfinite(vectorized.distance_km)
    assert np.array_equal(naive_finite, vec_finite)
    assert np.allclose(
        naive.distance_km[naive_finite],
        vectorized.distance_km[naive_finite],
        rtol=1e-12,
    )


@pytest.mark.parametrize("t_s", [0.0, 1000.0, 2500.0, 4000.0])
def test_default_config_sanity(t_s):
    config = Config()
    positions = node_positions(t_s, config)
    n_sats = topo_num_sats(config)
    graph = link_graph(positions, n_sats, config, t_s=t_s)

    sat_adj = graph.adjacency[:n_sats, :n_sats]

    # satellite subgraph connected: BFS from node 0
    visited = np.zeros(n_sats, dtype=bool)
    stack = [0]
    visited[0] = True
    while stack:
        node = stack.pop()
        for neighbor in np.flatnonzero(sat_adj[node]):
            if not visited[neighbor]:
                visited[neighbor] = True
                stack.append(neighbor)
    assert np.all(visited)

    mean_sat_links = sat_adj.sum() / n_sats
    assert 15 <= mean_sat_links <= 25

    ground_sat_adj = graph.adjacency[n_sats:, :n_sats]
    mean_sats_per_ground = ground_sat_adj.sum(axis=1).mean()
    assert 2 <= mean_sats_per_ground <= 5
