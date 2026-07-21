"""
Simplified circular-orbit topology model (Phase 1).

Positions are computed for N orbital planes x M satellites per plane,
evenly phased, constant angular velocity. No perturbations (SGP4 etc).
See docs/architecture.md for the full spec once you've written it.
"""
import numpy as np


def satellite_positions(t: float, config) -> np.ndarray:
    """
    Return an (N, 3) array of satellite positions at time t (seconds).

    TODO:
      for each plane p in range(config.num_planes):
          for each satellite index i in range(config.sats_per_plane):
              compute phase offset + angular position at time t
              convert to a 3D position given orbital radius / inclination / RAAN
    """
    raise NotImplementedError


def ground_station_positions(config) -> np.ndarray:
    """
    Return a (K, 3) array of fixed ground station positions.

    TODO: convert config.ground_stations (lat/lon pairs) to the same
    coordinate frame you use for satellites.
    """
    raise NotImplementedError


def orbital_period_s(config) -> float:
    """TODO: needed for the periodicity test in tests/test_topology.py."""
    raise NotImplementedError
