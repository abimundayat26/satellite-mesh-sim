"""
Phase 4 tests (SPEC.md §6): small fixed topology, hand-computed shortest
paths -- verify both Approach A (centralized) and Approach B (link-state)
converge to the correct routing table.
"""
import numpy as np
import pytest

from config import Config
from link.visibility import LinkGraph
from config import C_KM_S
from routing._dijkstra import dijkstra
from routing.centralized import CentralizedRouter, shortest_paths
from routing.link_state import LinkStateRouter


def _graph_from_edges_ms(v: int, num_sats: int, edges_ms, t_s: float = 0.0) -> LinkGraph:
    """Build a LinkGraph from a dict of {(i, j): latency_ms}."""
    distance_km = np.full((v, v), np.inf, dtype=np.float64)
    for (i, j), lat_ms in edges_ms.items():
        d = (lat_ms / 1000.0) * C_KM_S
        distance_km[i, j] = d
        distance_km[j, i] = d
    return LinkGraph(t_s=t_s, num_sats=num_sats, distance_km=distance_km)


# Fixed 5-node graph, all satellites. Latencies in ms:
# 0-1:1, 1-2:1, 0-2:3, 2-3:1, 1-3:4, 3-4:2
# Every shortest path is unique.
_FIXED_EDGES_MS = {
    (0, 1): 1.0,
    (1, 2): 1.0,
    (0, 2): 3.0,
    (2, 3): 1.0,
    (1, 3): 4.0,
    (3, 4): 2.0,
}

# Hand-derived shortest paths (worked by hand from the adjacency above):
#   Adjacency: 0:{1:1,2:3}  1:{0:1,2:1,3:4}  2:{0:3,1:1,3:1}  3:{2:1,1:4,4:2}  4:{3:2}
#
# From 0: to1=1 (direct); to2=min(1+1,3)=2 via 1; to3=min(2+1,1+4)=3 via 1->2;
#         to4=3+2=5 via 1->2->3.  -> dist=[0,1,2,3,5], next_hop=[0,1,1,1,1]
# From 1: to0=1 (direct); to2=1 (direct); to3=min(1+1,4)=2 via 2;
#         to4=2+2=4 via 2->3.      -> dist=[1,0,1,2,4], next_hop=[0,1,2,2,2]
# From 2: to0=min(1+1,3)=2 via 1; to1=1 (direct); to3=1 (direct); to4=1+2=3 via 3.
#                                  -> dist=[2,1,0,1,3], next_hop=[1,1,2,3,3]
# From 3: to0=min(1+3,4+1)=4 via 2->0; to1=min(1+1,4)=2 via 2; to2=1 (direct); to4=2 (direct).
#                                  -> dist=[4,2,1,0,2], next_hop=[2,2,2,3,4]
# From 4: to3=2 (direct); to2=2+1=3 via 3; to1=3+1=4 via 3->2; to0=4+1=... wait recompute below.
#         to1: via 3->2->1 = 2+1+1=4; to0: via 3->2->0 = 2+1+3=6 (cheaper than 3->1->0=2+4+1=7).
#                                  -> dist=[6,4,3,2,0], next_hop=[3,3,3,3,4]
_FIXED_DIST_S = np.array(
    [
        [0, 1, 2, 3, 5],
        [1, 0, 1, 2, 4],
        [2, 1, 0, 1, 3],
        [4, 2, 1, 0, 2],
        [6, 4, 3, 2, 0],
    ],
    dtype=np.float64,
) / 1000.0
_FIXED_NEXT_HOP = np.array(
    [
        [0, 1, 1, 1, 1],
        [0, 1, 2, 2, 2],
        [1, 1, 2, 3, 3],
        [2, 2, 2, 3, 4],
        [3, 3, 3, 3, 4],
    ],
    dtype=np.int32,
)


def _fixed_graph(t_s: float = 0.0) -> LinkGraph:
    return _graph_from_edges_ms(5, 5, _FIXED_EDGES_MS, t_s=t_s)


def _config_with_k(k: int) -> Config:
    cfg = Config()
    cfg.max_convergence_rounds = k
    return cfg


def test_centralized_matches_hand_computed_paths():
    graph = _fixed_graph()

    dist, next_hop = shortest_paths(graph, 0)
    np.testing.assert_allclose(dist, _FIXED_DIST_S[0], atol=1e-12)
    np.testing.assert_array_equal(next_hop, _FIXED_NEXT_HOP[0])

    router = CentralizedRouter()
    router.update(graph)
    table = router.next_hop_table()
    np.testing.assert_array_equal(table, _FIXED_NEXT_HOP)


def test_link_state_converges_to_correct_paths():
    graph = _fixed_graph()
    a_table = _FIXED_NEXT_HOP

    # Diameter of the fixed graph in hops is 4 (e.g. 4 -> 3 -> 2 -> 1 -> 0).
    router_k4 = LinkStateRouter(num_nodes=5, num_sats=5, config=_config_with_k(4))
    router_k4.update(graph)
    np.testing.assert_array_equal(router_k4.next_hop_table(), a_table)
    assert router_k4.stats()["converged"] is True

    # K=1: convergence is limited, so the first update leaves it unconverged.
    router_k1 = LinkStateRouter(num_nodes=5, num_sats=5, config=_config_with_k(1))
    router_k1.update(graph)
    assert router_k1.stats()["converged"] is False

    for _ in range(10):
        if router_k1.stats()["converged"]:
            break
        router_k1.update(graph)
    assert router_k1.stats()["converged"] is True
    np.testing.assert_array_equal(router_k1.next_hop_table(), a_table)


# 6-node chain graph: node 0's route to 5 depends on edge 3-5, two hops
# away, so a single K=1 round isn't enough to hear about its failure.
_CHAIN_EDGES_MS = {
    (0, 1): 1.0,
    (0, 2): 1.0,
    (1, 3): 1.0,
    (2, 4): 1.0,
    (3, 4): 1.0,
    (3, 5): 1.0,
    (4, 5): 5.0,
}


def test_link_state_link_failure_then_reconverges():
    graph = _graph_from_edges_ms(6, 6, _CHAIN_EDGES_MS)
    router_k1 = LinkStateRouter(num_nodes=6, num_sats=6, config=_config_with_k(1))
    for _ in range(10):
        router_k1.update(graph)
        if router_k1.stats()["converged"]:
            break
    assert router_k1.stats()["converged"] is True
    # Before failure, 0 -> 5 goes via node 1 (0-1-3-5 = 3ms vs 0-2-4-5 = 7ms).
    assert router_k1.next_hop_table()[0, 5] == 1

    failed_edges = dict(_CHAIN_EDGES_MS)
    del failed_edges[(3, 5)]
    failed_graph = _graph_from_edges_ms(6, 6, failed_edges)

    a_router = CentralizedRouter()
    a_router.update(failed_graph)
    a_table_new = a_router.next_hop_table()
    # After failure, the cheapest route is now via node 2 (0-2-4-5 = 7ms).
    assert a_table_new[0, 5] == 2

    router_k1.update(failed_graph)
    assert not np.array_equal(router_k1.next_hop_table(), a_table_new)
    assert router_k1.next_hop_table()[0, 5] == 1  # stale: hasn't heard yet

    for _ in range(10):
        if router_k1.stats()["converged"]:
            break
        router_k1.update(failed_graph)
    assert router_k1.stats()["converged"] is True
    np.testing.assert_array_equal(router_k1.next_hop_table(), a_table_new)


def test_ground_station_never_used_as_transit():
    # 3 satellites (0,1,2) + 1 ground station (3). The ground station offers
    # a much cheaper 0->2 path (1+1=2ms) that must never be used as transit.
    edges_ms = {
        (0, 1): 10.0,
        (1, 2): 10.0,
        (0, 3): 1.0,
        (3, 2): 1.0,
    }
    graph = _graph_from_edges_ms(4, 3, edges_ms)

    a_router = CentralizedRouter()
    a_router.update(graph)
    a_dist, a_next_hop = shortest_paths(graph, 0)
    assert a_next_hop[2] == 1
    np.testing.assert_allclose(a_dist[2], 0.020, atol=1e-12)

    b_router = LinkStateRouter(num_nodes=4, num_sats=3, config=_config_with_k(4))
    b_router.update(graph)
    assert b_router.next_hop_table()[0, 2] == 1


def test_dijkstra_rejects_zero_weight_edges():
    # On this graph, node 1 is reachable at equal cost via predecessor 3 or 2,
    # but a zero-weight edge lets the heap finalize node 1 before predecessor
    # 2's tie-break relaxation arrives. dijkstra() rejects zero weights instead.
    weight = np.array(
        [
            [np.inf, np.inf, np.inf, 3.0],
            [np.inf, np.inf, 0.0, 5.0],
            [np.inf, 0.0, np.inf, 5.0],
            [3.0, 5.0, 5.0, np.inf],
        ]
    )
    with pytest.raises(ValueError):
        dijkstra(weight, num_sats=4, source=0)


def test_dijkstra_rejects_negative_weight_edges():
    weight = np.array(
        [
            [np.inf, -1.0],
            [-1.0, np.inf],
        ]
    )
    with pytest.raises(ValueError):
        dijkstra(weight, num_sats=2, source=0)


def test_dijkstra_allows_inf_and_zero_diagonal():
    # The positive-weight guard must only apply to finite *off-diagonal*
    # entries -- np.inf (no edge) and the all-inf/implicit-zero diagonal
    # must not trip the check.
    weight = np.full((3, 3), np.inf)
    weight[0, 1] = weight[1, 0] = 2.0
    dist, next_hop = dijkstra(weight, num_sats=3, source=0)
    np.testing.assert_allclose(dist, [0.0, 2.0, np.inf])
    np.testing.assert_array_equal(next_hop, [0, 1, -1])


def test_dijkstra_matches_floyd_warshall_on_random_graphs():
    n = 20
    for seed in range(20):
        rng = np.random.default_rng(seed)

        # Random connected graph: start from a random spanning tree so
        # connectivity is guaranteed, then add extra random edges.
        distance_km = np.full((n, n), np.inf, dtype=np.float64)
        order = rng.permutation(n)
        for idx in range(1, n):
            i, j = int(order[idx]), int(order[rng.integers(0, idx)])
            d = float(rng.uniform(1.0, 1000.0))
            distance_km[i, j] = d
            distance_km[j, i] = d

        extra_pairs = rng.integers(0, n, size=(n * 2, 2))
        for i, j in extra_pairs:
            i, j = int(i), int(j)
            if i == j:
                continue
            d = float(rng.uniform(1.0, 1000.0))
            distance_km[i, j] = d
            distance_km[j, i] = d

        graph = LinkGraph(t_s=0.0, num_sats=n, distance_km=distance_km)

        # Independent brute-force reference: Floyd-Warshall over latency_s.
        fw = np.array(graph.latency_s, copy=True)
        np.fill_diagonal(fw, 0.0)
        for k in range(n):
            fw = np.minimum(fw, fw[:, k, None] + fw[None, k, :])

        for source in range(n):
            dist, _ = shortest_paths(graph, source)
            np.testing.assert_allclose(dist, fw[source], atol=1e-12)
