"""
Link / visibility model (Phase 2).

Given node positions at a timestep, determine which pairs have a valid
link (line-of-sight not blocked by Earth, within max range / elevation),
and the link latency.

This module's pairwise check is the O(N^2) hot path -- see cpp_ext/ for
the ported version (Phase 3).
"""
import numpy as np

EARTH_RADIUS_KM = 6371.0
SPEED_OF_LIGHT_KM_S = 299_792.458


def has_line_of_sight(pos_a: np.ndarray, pos_b: np.ndarray) -> bool:
    """
    True if the straight-line segment between pos_a and pos_b does not
    pass through Earth.

    TODO: closest-approach-of-segment-to-origin geometry check against
    EARTH_RADIUS_KM.
    """
    raise NotImplementedError


def in_range(pos_a: np.ndarray, pos_b: np.ndarray, max_range_km: float) -> bool:
    """TODO: simple distance check."""
    raise NotImplementedError


def link_latency_s(pos_a: np.ndarray, pos_b: np.ndarray) -> float:
    """TODO: distance / SPEED_OF_LIGHT_KM_S."""
    raise NotImplementedError


def link_graph(positions: np.ndarray, config) -> np.ndarray:
    """
    Build the full adjacency structure for one timestep.

    Naive version: nested loop over all pairs, calling has_line_of_sight
    + in_range. This is the function you'll benchmark against the C++
    version in Phase 3 -- consider also writing a numpy-vectorized
    version to compare against as a middle point.

    TODO: return an (N, N) adjacency matrix (bool or latency-valued).
    """
    raise NotImplementedError
