"""
Central configuration for the satellite mesh routing sim.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

EARTH_RADIUS_KM = 6371.0
MU_KM3_S2 = 398600.4418
C_KM_S = 299792.458

_DEFAULT_GROUND_STATIONS = [
    (47.6, -122.3),
    (40.6, -105.0),
    (51.5, -0.1),
    (1.35, 103.8),
    (-33.9, 151.2),
    (-26.2, 28.0),
]


@dataclass
class Config:
    # --- Constellation ---
    num_planes: int = 8
    sats_per_plane: int = 18
    altitude_km: float = 550.0
    inclination_deg: float = 53.0
    phasing_f: int = 1

    # --- Ground stations ---
    ground_stations: List[Tuple[float, float]] = field(
        default_factory=lambda: list(_DEFAULT_GROUND_STATIONS)
    )

    # --- Links ---
    max_isl_range_km: float = 5000.0
    min_elevation_deg: float = 10.0

    # --- Simulation ---
    duration_s: float = 12000.0
    timestep_s: float = 10.0
    random_seed: int = 42
    packets_per_step: int = 20
    packet_ttl_hops: int = 32
    use_cpp: bool = False

    # --- Routing ---
    max_convergence_rounds: int = 5

    # --- Fault injection ---
    fault_node_id: Optional[int] = None
    fault_time_s: Optional[float] = None


DEFAULT_CONFIG = Config()
