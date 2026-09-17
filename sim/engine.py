"""
Main simulation loop: ties together topology -> link graph -> routing ->
traffic injection -> metrics collection.
"""
from dataclasses import dataclass
from typing import Literal

import numpy as np

from link.visibility import LinkGraph, link_graph, link_graph_cpp
from routing._dijkstra import dijkstra
from routing.centralized import CentralizedRouter
from routing.link_state import LinkStateRouter
from sim.metrics import PacketRecord, PacketStatus, compute_metrics
from topology.orbits import node_positions, num_nodes, num_sats


@dataclass
class SimResult:
    metrics: dict
    per_step: dict
    packets: list


def _forward_packet(nh: np.ndarray, graph: LinkGraph, src: int, dst: int, ttl_hops: int):
    """Walk one packet hop-by-hop over `graph` using next-hop table `nh`.

    Returns (status, path, latency_s). latency_s is NaN unless delivered.
    """
    n = src
    path = [src]
    latency = 0.0
    while True:
        if n == dst:
            return PacketStatus.DELIVERED, tuple(path), latency
        if len(path) - 1 >= ttl_hops:
            return PacketStatus.DROPPED_TTL, tuple(path), float("nan")
        nxt = int(nh[n, dst])
        if nxt == -1:
            return PacketStatus.DROPPED_NO_ROUTE, tuple(path), float("nan")
        lat = graph.latency_s[n, nxt]
        if not np.isfinite(lat):
            return PacketStatus.DROPPED_LINK_DOWN, tuple(path), float("nan")
        latency += lat
        path.append(nxt)
        n = nxt


def run_simulation(config, router: Literal["centralized", "link_state"] = "link_state") -> SimResult:
    n_sats = num_sats(config)
    n_nodes = num_nodes(config)
    ground_ids = list(range(n_sats, n_nodes))

    if router == "centralized":
        rt = CentralizedRouter()
    elif router == "link_state":
        rt = LinkStateRouter(n_nodes, n_sats, config)
    else:
        raise ValueError(f"unknown router: {router!r}")

    rng = np.random.default_rng(config.random_seed)
    num_steps = int(config.duration_s // config.timestep_s)

    dead = set()
    fault_applied = False

    packets = []
    packet_id = 0

    per_step = {
        "t_s": np.zeros(num_steps),
        "packets_sent": np.zeros(num_steps),
        "packets_delivered": np.zeros(num_steps),
        "delivery_ratio": np.full(num_steps, np.nan),
        "delivery_ratio_reachable": np.full(num_steps, np.nan),
        "mean_latency_s": np.full(num_steps, np.nan),
        "mean_hops": np.full(num_steps, np.nan),
        "misrouted_frac": np.full(num_steps, np.nan),
        "unreachable_frac": np.full(num_steps, np.nan),
        "route_divergence_frac": np.zeros(num_steps),
        "converged": np.full(num_steps, np.nan),
        "rounds_to_converge": np.full(num_steps, np.nan),
    }

    for k in range(num_steps):
        t_s = k * config.timestep_s
        per_step["t_s"][k] = t_s

        positions = node_positions(t_s, config)
        if config.use_cpp:
            graph = link_graph_cpp(positions, n_sats, config, t_s=t_s)
        else:
            graph = link_graph(positions, n_sats, config, t_s=t_s)

        if (
            config.fault_node_id is not None
            and config.fault_time_s is not None
            and t_s >= config.fault_time_s
        ):
            dead.add(config.fault_node_id)

        if dead:
            dist_km = graph.distance_km.copy()
            for nid in dead:
                dist_km[nid, :] = np.inf
                dist_km[:, nid] = np.inf
            graph = LinkGraph(t_s=graph.t_s, num_sats=graph.num_sats, distance_km=dist_km)

        if config.fault_node_id is not None and config.fault_node_id in dead and not fault_applied:
            rt.kill(config.fault_node_id)
            fault_applied = True

        rt.update(graph)
        nh = rt.next_hop_table()

        live_ground = [g for g in ground_ids if g not in dead]

        optimal = {}
        for src in live_ground:
            dist_true, _ = dijkstra(graph.latency_s, n_sats, src)
            optimal[src] = dist_true

        num_pairs = 0
        num_divergent = 0
        for src in live_ground:
            for dst in live_ground:
                if src == dst:
                    continue
                opt = optimal[src][dst]
                if not np.isfinite(opt):
                    continue
                num_pairs += 1
                status, _, latency = _forward_packet(nh, graph, src, dst, config.packet_ttl_hops)
                if status is not PacketStatus.DELIVERED or latency > opt + 1e-12:
                    num_divergent += 1
        per_step["route_divergence_frac"][k] = (
            num_divergent / num_pairs if num_pairs else 0.0
        )

        step_pairs = []
        if len(live_ground) >= 2:
            for _ in range(config.packets_per_step):
                src, dst = rng.choice(live_ground, size=2, replace=False)
                step_pairs.append((int(src), int(dst)))

        step_delivered = 0
        step_reachable = 0
        step_misrouted = 0
        step_latencies = []
        step_hops = []

        for src, dst in step_pairs:
            opt_latency = optimal[src][dst]
            reachable = bool(np.isfinite(opt_latency))

            status, path, latency_s = _forward_packet(nh, graph, src, dst, config.packet_ttl_hops)
            delivered = status is PacketStatus.DELIVERED
            misrouted = reachable and (not delivered or latency_s > opt_latency + 1e-12)

            packets.append(
                PacketRecord(
                    packet_id=packet_id,
                    t_s=t_s,
                    src=src,
                    dst=dst,
                    status=status,
                    path=path,
                    hops=len(path) - 1,
                    latency_s=latency_s,
                    optimal_latency_s=opt_latency if reachable else float("nan"),
                    reachable=reachable,
                    misrouted=misrouted,
                )
            )
            packet_id += 1

            if reachable:
                step_reachable += 1
            if misrouted:
                step_misrouted += 1
            if delivered:
                step_delivered += 1
                step_latencies.append(latency_s)
                step_hops.append(len(path) - 1)

        sent = len(step_pairs)
        per_step["packets_sent"][k] = sent
        per_step["packets_delivered"][k] = step_delivered
        if sent:
            per_step["delivery_ratio"][k] = step_delivered / sent
            per_step["unreachable_frac"][k] = (sent - step_reachable) / sent
        if step_reachable:
            per_step["delivery_ratio_reachable"][k] = step_delivered / step_reachable
            per_step["misrouted_frac"][k] = step_misrouted / step_reachable
        if step_latencies:
            per_step["mean_latency_s"][k] = float(np.mean(step_latencies))
            per_step["mean_hops"][k] = float(np.mean(step_hops))

        if router == "link_state":
            stats = rt.stats()
            per_step["converged"][k] = 1.0 if stats["converged"] else 0.0
            per_step["rounds_to_converge"][k] = stats["rounds_since_change"]

    metrics = compute_metrics(
        packets,
        per_step["route_divergence_frac"],
        per_step["converged"],
        per_step["rounds_to_converge"],
    )

    return SimResult(metrics=metrics, per_step=per_step, packets=packets)
