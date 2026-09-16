"""
Link / visibility model (Phase 2). See SPEC.md §4, §5.2.

Given node positions at a timestep, determine which pairs have a valid
link (line-of-sight not blocked by Earth, within max range / elevation),
and the link latency.

This module's pairwise check is the O(N^2) hot path -- see cpp_ext/ for
the ported version (Phase 3).
"""
from dataclasses import dataclass

import numpy as np

from config import C_KM_S, EARTH_RADIUS_KM


def has_line_of_sight(pos_a: np.ndarray, pos_b: np.ndarray, earth_radius_km: float) -> bool:
    """True if the segment between pos_a and pos_b does not pass through Earth."""
    a = np.asarray(pos_a, dtype=np.float64)
    b = np.asarray(pos_b, dtype=np.float64)
    d = b - a
    d_sq = d @ d
    if d_sq == 0.0:
        raise ValueError("has_line_of_sight: pos_a and pos_b are the same position")
    s = np.clip(-(a @ d) / d_sq, 0.0, 1.0)
    closest = a + s * d
    return bool(np.linalg.norm(closest) >= earth_radius_km)


def in_range(pos_a: np.ndarray, pos_b: np.ndarray, max_range_km: float) -> bool:
    a = np.asarray(pos_a, dtype=np.float64)
    b = np.asarray(pos_b, dtype=np.float64)
    return bool(np.linalg.norm(b - a) <= max_range_km)


def elevation_deg(ground: np.ndarray, sat: np.ndarray) -> float:
    g = np.asarray(ground, dtype=np.float64)
    s = np.asarray(sat, dtype=np.float64)
    v = s - g
    v_norm = np.linalg.norm(v)
    if v_norm == 0.0:
        raise ValueError("elevation_deg: ground and sat are the same position")
    g_hat = g / np.linalg.norm(g)
    sin_el = (g_hat @ v) / v_norm
    return float(np.degrees(np.arcsin(np.clip(sin_el, -1.0, 1.0))))


def link_latency_s(pos_a: np.ndarray, pos_b: np.ndarray) -> float:
    a = np.asarray(pos_a, dtype=np.float64)
    b = np.asarray(pos_b, dtype=np.float64)
    return float(np.linalg.norm(b - a) / C_KM_S)


@dataclass(frozen=True)
class LinkGraph:
    t_s: float
    num_sats: int
    distance_km: np.ndarray  # (V, V) float64, symmetric, inf = no link / diagonal

    @property
    def adjacency(self) -> np.ndarray:
        return np.isfinite(self.distance_km)

    @property
    def latency_s(self) -> np.ndarray:
        return self.distance_km / C_KM_S

    def neighbors(self, n: int) -> np.ndarray:
        return np.flatnonzero(self.adjacency[n])


def _classify(i: int, j: int, num_sats: int) -> str:
    if i < num_sats and j < num_sats:
        return "sat-sat"
    if i < num_sats or j < num_sats:
        return "sat-ground"
    return "ground-ground"


def link_graph_naive(positions: np.ndarray, num_sats: int, config, t_s: float = 0.0) -> LinkGraph:
    """Loops over every pair. Used as the reference for parity checks."""
    v = positions.shape[0]
    distance_km = np.full((v, v), np.inf, dtype=np.float64)

    for i in range(v):
        for j in range(i + 1, v):
            kind = _classify(i, j, num_sats)
            if kind == "ground-ground":
                continue

            a = positions[i]
            b = positions[j]

            if kind == "sat-sat":
                if not in_range(a, b, config.max_isl_range_km):
                    continue
                if not has_line_of_sight(a, b, EARTH_RADIUS_KM):
                    continue
            else:  # sat-ground; i < j and kind is sat-ground implies i is the satellite
                sat, ground = a, b
                if elevation_deg(ground, sat) < config.min_elevation_deg:
                    continue

            d = float(np.linalg.norm(b - a))
            distance_km[i, j] = d
            distance_km[j, i] = d

    return LinkGraph(t_s=t_s, num_sats=num_sats, distance_km=distance_km)


def link_graph(positions: np.ndarray, num_sats: int, config, t_s: float = 0.0) -> LinkGraph:
    """Numpy-vectorized reference implementation. No Python loop over pairs."""
    positions = np.asarray(positions, dtype=np.float64)
    v = positions.shape[0]

    diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]  # diff[i, j] = pos_j - pos_i
    dist = np.linalg.norm(diff, axis=2)

    # closest approach of segment i->j to the origin
    a_dot_d = np.einsum("ik,ijk->ij", positions, diff)
    d_sq = np.einsum("ijk,ijk->ij", diff, diff)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where(d_sq > 0, np.clip(-a_dot_d / np.where(d_sq > 0, d_sq, 1.0), 0.0, 1.0), 0.0)
    closest = positions[:, np.newaxis, :] + s[:, :, np.newaxis] * diff
    closest_norm = np.linalg.norm(closest, axis=2)
    los_ok = closest_norm >= EARTH_RADIUS_KM

    is_sat = np.arange(v) < num_sats
    sat_sat_mask = is_sat[:, np.newaxis] & is_sat[np.newaxis, :]
    ground_ground_mask = (~is_sat)[:, np.newaxis] & (~is_sat)[np.newaxis, :]
    sat_ground_mask = ~sat_sat_mask & ~ground_ground_mask

    sat_sat_ok = sat_sat_mask & (dist <= config.max_isl_range_km) & los_ok

    # elevation: sin(el) = g_hat . (sat - ground) / |sat - ground|
    # diff[i,j] = pos_j - pos_i; for ground i, sat j this is (sat - ground) as needed.
    norms = np.linalg.norm(positions, axis=1, keepdims=True)
    g_hat = positions / norms
    with np.errstate(invalid="ignore", divide="ignore"):
        sin_el = np.einsum("ik,ijk->ij", g_hat, diff) / np.where(dist > 0, dist, 1.0)
    elevation = np.degrees(np.arcsin(np.clip(sin_el, -1.0, 1.0)))
    # For pair (i,j) with i ground, j sat: use elevation[i,j] (viewed from ground i).
    # For pair (i,j) with i sat, j ground: use elevation[j,i] (viewed from ground j).
    ground_is_i = (~is_sat)[:, np.newaxis] & is_sat[np.newaxis, :]
    elevation_view = np.where(ground_is_i, elevation, elevation.T)
    sat_ground_ok = sat_ground_mask & (elevation_view >= config.min_elevation_deg)

    ok = sat_sat_ok | sat_ground_ok
    np.fill_diagonal(ok, False)

    distance_km = np.where(ok, dist, np.inf)

    return LinkGraph(t_s=t_s, num_sats=num_sats, distance_km=distance_km)


def link_graph_cpp(positions: np.ndarray, num_sats: int, config, t_s: float = 0.0) -> LinkGraph:
    """Wraps the C++ extension (Phase 3). Same output as link_graph()."""
    import visibility_ext  # lazy: keeps this module importable when the ext isn't built

    positions = np.asarray(positions, dtype=np.float64)
    distance_km = visibility_ext.link_distances(
        positions,
        num_sats,
        config.max_isl_range_km,
        config.min_elevation_deg,
        EARTH_RADIUS_KM,
    )
    return LinkGraph(t_s=t_s, num_sats=num_sats, distance_km=distance_km)
