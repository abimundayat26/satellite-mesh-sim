"""
Central configuration for the satellite mesh routing sim.

Fill in the constants once and treat this as ground truth for every
other module -- topology, link, routing, and sim should all import
from here rather than hardcoding numbers.
"""
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Config:
    # --- Constellation ---
    num_planes: int = 0          # TODO: pick a value (Phase 0)
    sats_per_plane: int = 0      # TODO
    altitude_km: float = 0.0     # TODO
    inclination_deg: float = 0.0  # TODO

    # --- Ground stations ---
    ground_stations: List[Tuple[float, float]] = field(default_factory=list)
    # TODO: list of (lat_deg, lon_deg)

    # --- Links ---
    max_isl_range_km: float = 0.0   # TODO: max inter-satellite link range
    min_elevation_deg: float = 0.0  # TODO: min elevation for sat-ground link

    # --- Simulation ---
    duration_s: float = 0.0      # TODO
    timestep_s: float = 0.0      # TODO
    random_seed: int = 42

    # --- Routing (Phase 4) ---
    max_convergence_rounds: int = 0  # TODO: bound on link-state exchange rounds


DEFAULT_CONFIG = Config()
