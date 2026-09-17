"""
Circular-orbit Walker-delta constellation: N planes x M satellites,
constant angular velocity, no perturbations, non-rotating Earth.
"""
import numpy as np

from config import EARTH_RADIUS_KM, MU_KM3_S2


def orbit_radius_km(config) -> float:
    return EARTH_RADIUS_KM + config.altitude_km


def orbital_period_s(config) -> float:
    r_orbit_km = orbit_radius_km(config)
    return 2 * np.pi * np.sqrt(r_orbit_km**3 / MU_KM3_S2)


def num_sats(config) -> int:
    return config.num_planes * config.sats_per_plane


def num_nodes(config) -> int:
    return num_sats(config) + len(config.ground_stations)


def satellite_positions(t_s: float, config) -> np.ndarray:
    """Positions of all N*M satellites at time t_s, id = p*M + i."""
    n_planes = config.num_planes
    m_sats = config.sats_per_plane
    r = orbit_radius_km(config)
    inc = np.radians(config.inclination_deg)
    period_s = orbital_period_s(config)

    p_idx = np.repeat(np.arange(n_planes), m_sats)
    i_idx = np.tile(np.arange(m_sats), n_planes)

    u = (
        2 * np.pi * i_idx / m_sats
        + 2 * np.pi * config.phasing_f * p_idx / (n_planes * m_sats)
        + 2 * np.pi * t_s / period_s
    )
    omega_p = 2 * np.pi * p_idx / n_planes

    x0 = r * np.cos(u)
    y0 = r * np.sin(u)

    # Rx(inc)
    y1 = np.cos(inc) * y0
    z1 = np.sin(inc) * y0

    # Rz(omega_p)
    x2 = np.cos(omega_p) * x0 - np.sin(omega_p) * y1
    y2 = np.sin(omega_p) * x0 + np.cos(omega_p) * y1
    z2 = z1

    return np.ascontiguousarray(np.stack([x2, y2, z2], axis=1))


def ground_station_positions(config) -> np.ndarray:
    """Fixed positions of ground stations on the Earth's surface."""
    stations = np.asarray(config.ground_stations, dtype=np.float64)
    lat = np.radians(stations[:, 0])
    lon = np.radians(stations[:, 1])

    x = EARTH_RADIUS_KM * np.cos(lat) * np.cos(lon)
    y = EARTH_RADIUS_KM * np.cos(lat) * np.sin(lon)
    z = EARTH_RADIUS_KM * np.sin(lat)

    return np.ascontiguousarray(np.stack([x, y, z], axis=1))


def node_positions(t_s: float, config) -> np.ndarray:
    """Satellites first, then ground stations."""
    return np.ascontiguousarray(
        np.vstack([satellite_positions(t_s, config), ground_station_positions(config)])
    )
