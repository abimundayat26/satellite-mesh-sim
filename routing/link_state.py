"""
Approach B -- distributed link-state routing (Phase 4, SPEC.md §5.4).

Each node keeps its own link-state database (lsdb) and outbox *across
timesteps*. On update(): originate LSAs on neighbour-set change, flood
synchronously for K = config.max_convergence_rounds rounds (leftover
outbox carries over to the next timestep's graph), then each node runs
Dijkstra on its own view.

Staleness and flapping are intended, measured behaviour -- see SPEC.md §7.
Don't "fix" them.
"""
from dataclasses import dataclass

import numpy as np

from link.visibility import LinkGraph
from routing._dijkstra import dijkstra


@dataclass(frozen=True)
class LSA:
    origin: int
    seq: int
    links: tuple  # tuple[tuple[int, float], ...], sorted by neighbour id


class LinkStateRouter:
    def __init__(self, num_nodes: int, num_sats: int, config):
        self.num_nodes = num_nodes
        self.num_sats = num_sats
        self.config = config

        self.alive = [True] * num_nodes
        self.lsdb = [dict() for _ in range(num_nodes)]
        self.outbox = [[] for _ in range(num_nodes)]
        self.own_seq = [0] * num_nodes
        self.last_neighbor_set = [None] * num_nodes

        self._global_round = 0
        self._last_origination_round = 0
        self._latest_seq_true = [0] * num_nodes

        self._next_hop = np.full((num_nodes, num_nodes), -1, dtype=np.int32)
        for s in range(num_nodes):
            self._next_hop[s, s] = s

        self._last_graph = None

    def kill(self, node_id: int) -> None:
        self.alive[node_id] = False
        self.lsdb[node_id] = {}
        self.outbox[node_id] = []
        self._next_hop[node_id, :] = -1
        self._next_hop[node_id, node_id] = node_id

    def update(self, graph: LinkGraph) -> None:
        self._originate(graph)
        self._flood(graph)
        self._recompute_routes(graph)
        self._last_graph = graph

    def next_hop_table(self) -> np.ndarray:
        return self._next_hop

    def _originate(self, graph: LinkGraph) -> None:
        for n in range(self.num_nodes):
            if not self.alive[n]:
                continue
            neighbor_ids = graph.neighbors(n)
            neighbor_set = frozenset(int(x) for x in neighbor_ids)
            if neighbor_set == self.last_neighbor_set[n]:
                continue

            seq = self.own_seq[n] + 1
            self.own_seq[n] = seq
            links = tuple(
                sorted((int(nb), float(graph.latency_s[n, nb])) for nb in neighbor_ids)
            )
            lsa = LSA(origin=n, seq=seq, links=links)
            self.lsdb[n][n] = lsa
            self.outbox[n].append(lsa)
            self.last_neighbor_set[n] = neighbor_set
            self._latest_seq_true[n] = seq
            self._last_origination_round = self._global_round

    def _flood(self, graph: LinkGraph) -> None:
        k = self.config.max_convergence_rounds
        for _ in range(k):
            incoming = [[] for _ in range(self.num_nodes)]
            for n in range(self.num_nodes):
                if not self.alive[n] or not self.outbox[n]:
                    continue
                for nb in graph.neighbors(n):
                    nb = int(nb)
                    if self.alive[nb]:
                        incoming[nb].extend(self.outbox[n])
                self.outbox[n] = []

            self._global_round += 1

            for n in range(self.num_nodes):
                if not self.alive[n]:
                    continue
                for lsa in incoming[n]:
                    existing = self.lsdb[n].get(lsa.origin)
                    if existing is None or lsa.seq > existing.seq:
                        self.lsdb[n][lsa.origin] = lsa
                        self.outbox[n].append(lsa)

    def _own_view_weights(self, n: int, graph: LinkGraph) -> np.ndarray:
        v = self.num_nodes
        w = np.full((v, v), np.inf, dtype=np.float64)

        for nb in graph.neighbors(n):
            nb = int(nb)
            lat = float(graph.latency_s[n, nb])
            w[n, nb] = lat
            w[nb, n] = lat

        lsdb_n = self.lsdb[n]
        for i in range(v):
            if i == n or not self.alive[i]:
                continue
            lsa_i = lsdb_n.get(i)
            if lsa_i is None:
                continue
            links_i = dict(lsa_i.links)
            for j, lat_i in links_i.items():
                if j == n or j <= i:
                    continue
                if not self.alive[j]:
                    continue
                lsa_j = lsdb_n.get(j)
                if lsa_j is None:
                    continue
                links_j = dict(lsa_j.links)
                lat_j = links_j.get(i)
                if lat_j is None:
                    continue
                avg = (lat_i + lat_j) / 2.0
                w[i, j] = avg
                w[j, i] = avg

        return w

    def _recompute_routes(self, graph: LinkGraph) -> None:
        v = self.num_nodes
        nh = np.full((v, v), -1, dtype=np.int32)
        for s in range(v):
            nh[s, s] = s

        for n in range(v):
            if not self.alive[n]:
                continue
            weight = self._own_view_weights(n, graph)
            _, next_hop = dijkstra(weight, self.num_sats, n)
            nh[n, :] = next_hop

        self._next_hop = nh

    def stats(self) -> dict:
        pending_lsas = sum(
            len(self.outbox[n]) for n in range(self.num_nodes) if self.alive[n]
        )

        converged = pending_lsas == 0
        if converged and self._last_graph is not None:
            graph = self._last_graph
            for n in range(self.num_nodes):
                if not self.alive[n]:
                    continue
                dist_true, _ = dijkstra(graph.latency_s, self.num_sats, n)
                for m in range(self.num_nodes):
                    if m == n or not self.alive[m]:
                        continue
                    if not np.isfinite(dist_true[m]):
                        continue
                    lsa = self.lsdb[n].get(m)
                    if lsa is None or lsa.seq < self._latest_seq_true[m]:
                        converged = False
                        break
                if not converged:
                    break

        return {
            "converged": converged,
            "rounds_since_change": self._global_round - self._last_origination_round,
            "pending_lsas": pending_lsas,
        }
