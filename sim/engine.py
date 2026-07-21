"""
Main simulation loop (Phase 5).

Ties together topology -> link graph -> routing -> traffic injection
-> metrics collection.
"""


def run_simulation(config, routing_approach: str = "link_state") -> dict:
    """
    TODO:
      for t in range(0, config.duration_s, config.timestep_s):
          positions = topology.satellite_positions(t, config)  # + ground stations
          adjacency = link.visibility.link_graph(positions, config)  # or cpp_ext version
          update routing tables (centralized or link_state)
          inject traffic, route packets hop-by-hop
          record per-packet outcome

    Returns a metrics dict -- see sim/metrics.py.
    """
    raise NotImplementedError


def inject_fault(config, t_fail: float, node_id: int):
    """TODO: Phase 6 -- remove a node from the topology at t_fail, keep simulating."""
    raise NotImplementedError
