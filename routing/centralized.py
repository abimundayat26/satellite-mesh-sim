"""
Approach A -- centralized baseline. Recomputes global shortest paths every
timestep from the true graph; an oracle upper bound to compare B against.
"""
import numpy as np

from link.visibility import LinkGraph
from routing._dijkstra import dijkstra


def shortest_paths(graph: LinkGraph, source: int):
    """Dijkstra over the true graph. Returns (dist_s (V,), next_hop (V,) int32)."""
    return dijkstra(graph.latency_s, graph.num_sats, source)


class CentralizedRouter:
    def __init__(self):
        self._next_hop = None
        self._dead = set()

    def update(self, graph: LinkGraph) -> None:
        v = graph.distance_km.shape[0]
        nh = np.full((v, v), -1, dtype=np.int32)
        for s in range(v):
            _, next_hop = shortest_paths(graph, s)
            nh[s, :] = next_hop
        for node_id in self._dead:
            nh[node_id, :] = -1
            nh[node_id, node_id] = node_id
        self._next_hop = nh

    def next_hop_table(self) -> np.ndarray:
        if self._next_hop is None:
            raise RuntimeError("update() must be called before next_hop_table()")
        return self._next_hop

    def kill(self, node_id: int) -> None:
        self._dead.add(node_id)
        if self._next_hop is not None:
            self._next_hop[node_id, :] = -1
            self._next_hop[node_id, node_id] = node_id
