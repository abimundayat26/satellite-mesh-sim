"""
Approach A -- centralized/reactive baseline (Phase 4).

Recomputes global shortest paths from scratch every timestep, given
complete topology knowledge. Unrealistic but gives you an upper bound
to compare Approach B against.
"""


def shortest_paths(adjacency, source) -> dict:
    """
    TODO: Dijkstra (or similar) over the current adjacency structure.
    Return {destination_node: next_hop} for the given source.
    """
    raise NotImplementedError
