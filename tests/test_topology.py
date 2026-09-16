"""Phase 1 tests: known positions at t=0, periodicity at t=T. See SPEC.md §6."""
import numpy as np

from config import Config, EARTH_RADIUS_KM
from topology.orbits import (
    ground_station_positions,
    node_positions,
    num_nodes,
    num_sats,
    orbit_radius_km,
    orbital_period_s,
    satellite_positions,
)


def test_position_at_t0_matches_hand_computed():
    config = Config()
    r = orbit_radius_km(config)

    positions = satellite_positions(0.0, config)

    # Satellite 0 (plane 0, slot 0): u=0, omega=0 -> straight down +x axis.
    np.testing.assert_allclose(positions[0], [r, 0.0, 0.0], atol=1e-6)


def test_position_at_t0_hand_computed_p1_i1():
    config = Config()  # N=8, M=18, F=1, inclination=53 deg
    r = orbit_radius_km(config)
    n_planes, m_sats, f = config.num_planes, config.sats_per_plane, config.phasing_f
    inc = np.radians(config.inclination_deg)

    # Satellite id = p*M + i = 1*18 + 1 = 19.
    p, i = 1, 1
    # u = 2*pi*i/M + 2*pi*F*p/(N*M) + 2*pi*t/T, t=0
    #   = 2*pi*1/18 + 2*pi*1*1/(8*18) = 2*pi*(1/18 + 1/144) = 2*pi*9/144 = pi/8
    u = 2 * np.pi * i / m_sats + 2 * np.pi * f * p / (n_planes * m_sats)
    # omega_p = 2*pi*p/N = 2*pi/8 = pi/4
    omega_p = 2 * np.pi * p / n_planes

    # pos = Rz(omega_p) . Rx(inc) . [r cos(u), r sin(u), 0]
    x0, y0 = r * np.cos(u), r * np.sin(u)
    y1, z1 = np.cos(inc) * y0, np.sin(inc) * y0  # Rx(inc)
    x2 = np.cos(omega_p) * x0 - np.sin(omega_p) * y1  # Rz(omega_p)
    y2 = np.sin(omega_p) * x0 + np.cos(omega_p) * y1
    z2 = z1

    expected = np.array([x2, y2, z2])  # ~= [3394.276485, 5648.445795, 2115.227706]

    positions = satellite_positions(0.0, config)
    sat_id = p * m_sats + i
    np.testing.assert_allclose(positions[sat_id], expected, atol=1e-6)


def test_periodicity():
    config = Config()
    period_s = orbital_period_s(config)

    pos_t0 = satellite_positions(0.0, config)
    pos_tT = satellite_positions(period_s, config)

    np.testing.assert_allclose(pos_tT, pos_t0, atol=1e-6)


def test_shapes_and_dtypes():
    config = Config()
    n_sats = num_sats(config)
    n_ground = len(config.ground_stations)
    n_total = num_nodes(config)

    sat_pos = satellite_positions(0.0, config)
    ground_pos = ground_station_positions(config)
    all_pos = node_positions(0.0, config)

    assert sat_pos.shape == (n_sats, 3)
    assert ground_pos.shape == (n_ground, 3)
    assert all_pos.shape == (n_total, 3)
    for arr in (sat_pos, ground_pos, all_pos):
        assert arr.dtype == np.float64
        assert arr.flags["C_CONTIGUOUS"]


def test_satellite_radius_and_ground_station_radius():
    config = Config()
    r = orbit_radius_km(config)

    sat_pos = satellite_positions(0.0, config)
    sat_radii = np.linalg.norm(sat_pos, axis=1)
    np.testing.assert_allclose(sat_radii, r, rtol=1e-12)

    ground_pos = ground_station_positions(config)
    ground_radii = np.linalg.norm(ground_pos, axis=1)
    np.testing.assert_allclose(ground_radii, EARTH_RADIUS_KM, rtol=1e-12)


def test_min_intersatellite_distance_over_one_orbit():
    config = Config()
    period_s = orbital_period_s(config)

    min_dist = np.inf
    t_s = 0.0
    while t_s <= period_s:
        pos = satellite_positions(t_s, config)
        diffs = pos[:, None, :] - pos[None, :, :]
        dists = np.linalg.norm(diffs, axis=-1)
        np.fill_diagonal(dists, np.inf)
        min_dist = min(min_dist, dists.min())
        t_s += 30.0

    # SPEC measured ~128.6 km with phasing_f=1.
    assert min_dist > 100.0
