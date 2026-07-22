"""
Simplified circular-orbit topology model (Phase 1).

Positions are computed for N orbital planes x M satellites per plane,
evenly phased, constant angular velocity. No perturbations (SGP4 etc).
See docs/architecture.md for the full spec once you've written it.
"""
import numpy as np

# Compute satellite positions in 3D space at time t
def satellite_positions(t: float, config) -> np.ndarray:
    sat_positions = []
    for p in range(config.num_planes):
        for i in range(config.sats_per_plane):
            phase_offset = 2 * np.pi * i / config.sats_per_plane
            angular_position = phase_offset + 2 * np.pi * t / config.orbital_period_s
            x = config.r_orbit_km * np.cos(angular_position)
            y = config.r_orbit_km * np.sin(angular_position)
            z = y  * np.sin(np.radians(config.inclination_deg))
            y *= np.cos(np.radians(config.inclination_deg))
            omega = 2 * np.pi * p / config.num_planes
            x_temp = x
            y_temp = y
            x = x * np.cos(omega) - y * np.sin(omega)
            y = x_temp * np.sin(omega) + y_temp * np.cos(omega)
            sat_positions.append((x, y, z))
    return np.array(sat_positions)

# Return an array of ground station positions (lat/long to xyz)
def ground_station_positions(config) -> np.ndarray:
    ground_station_positions = []
    for lat, lon in config.ground_stations:
        x = config.r_earth_km * np.cos(np.radians(lat)) * np.cos(np.radians(lon))
        y = config.r_earth_km * np.cos(np.radians(lat)) * np.sin(np.radians(lon))
        z = config.r_earth_km * np.sin(np.radians(lat))
        ground_station_positions.append((x, y, z))
    return np.array(ground_station_positions)


def orbital_period_s(config) -> float:
    return config.orbital_period_s
