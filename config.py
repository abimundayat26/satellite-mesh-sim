"""
Central configuration for the satellite mesh routing sim.
"""
from dataclasses import dataclass, field
from typing import List, Tuple
import numpy as np


@dataclass
class Config:
    # --- Constellation ---
    num_planes: int = 8          
    sats_per_plane: int = 18      
    altitude_km: float = 550.0     
    inclination_deg: float = 53.0  

    # --- Ground stations ---
    ground_stations: List[Tuple[float, float]] = field(default_factory=list)

    # --- Links ---
    max_isl_range_km: float = 2000.0
    min_elevation_deg: float = 25.0  

    # --- Simulation ---
    duration_s: float = 12000.0      
    timestep_s: float = 10.0      
    random_seed: int = 42

    # --- Routing ---
    max_convergence_rounds: int = 5

    # --- Constants ---
    mu = 398600.4418
    r_earth_km = 6371.0
    r_orbit_km = r_earth_km + altitude_km
    def __post_init__(self):
        self.ground_stations.append((47.6, -122.3))
        self.ground_stations.append((40.6, -105.0))
        self.ground_stations.append((51.5, -0.1))
        self.ground_stations.append((1.35, 103.8))
        self.ground_stations.append((-33.9, 151.2))
        self.ground_stations.append((-26.2, 28))


DEFAULT_CONFIG = Config()
