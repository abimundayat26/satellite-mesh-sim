"""
Shared hand-written Dijkstra used by both Approach A and Approach B
(SPEC.md §5.4), so their tie-break and ground-station-transit rules can
never drift apart.
"""
import heapq

import numpy as np


def dijkstra(weight: np.ndarray, num_sats: int, source: int):
    """Single-source shortest paths over `weight` ((V,V) float64, inf = no edge).

    Returns (dist_s: (V,) float64, next_hop: (V,) int32).
    Ties go to the lowest predecessor ID. Ground stations (id >= num_sats)
    are never used as a transit hop -- only expanded when they are the
    source itself.

    Requires every finite off-diagonal edge weight to be strictly positive.
    The lowest-predecessor-ID tie-break relies on this: a node offering an
    equal-cost alternate path must have a strictly smaller finalized
    distance than the node it reaches, which is what guarantees it is
    popped from the heap (and its tie-break relaxation applied) before the
    reached node is marked visited. A zero (or negative) weight edge can
    break that ordering and cause the tie-break to be silently skipped.
    """
    v = weight.shape[0]
    off_diagonal = ~np.eye(v, dtype=bool)
    finite_off_diagonal = np.isfinite(weight) & off_diagonal
    if np.any(weight[finite_off_diagonal] <= 0.0):
        raise ValueError(
            "dijkstra: all finite edge weights must be strictly positive "
            "(zero/negative weights break the lowest-predecessor-ID tie-break)"
        )

    dist = np.full(v, np.inf, dtype=np.float64)
    next_hop = np.full(v, -1, dtype=np.int32)
    pred = np.full(v, -1, dtype=np.int32)

    dist[source] = 0.0
    next_hop[source] = source
    pred[source] = source

    visited = np.zeros(v, dtype=bool)
    heap = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if visited[u]:
            continue
        visited[u] = True

        if u != source and u >= num_sats:
            # Ground station reached as a destination: never expand it as a
            # transit hop.
            continue

        row = weight[u]
        for w in np.flatnonzero(np.isfinite(row)):
            w = int(w)
            if visited[w]:
                continue
            cand = d + row[w]
            if cand < dist[w]:
                dist[w] = cand
                pred[w] = u
                next_hop[w] = w if u == source else next_hop[u]
                heapq.heappush(heap, (cand, w))
            elif cand == dist[w] and u < pred[w]:
                pred[w] = u
                next_hop[w] = w if u == source else next_hop[u]

    return dist, next_hop
