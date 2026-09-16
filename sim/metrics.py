"""
Metrics aggregation (Phase 5/6). See SPEC.md §4, §5.5.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

import numpy as np


class PacketStatus(Enum):
    DELIVERED = "delivered"
    DROPPED_NO_ROUTE = "dropped_no_route"
    DROPPED_LINK_DOWN = "dropped_link_down"
    DROPPED_TTL = "dropped_ttl"


@dataclass
class PacketRecord:
    packet_id: int
    t_s: float
    src: int
    dst: int
    status: PacketStatus
    path: Tuple[int, ...]
    hops: int
    latency_s: float  # NaN if not delivered
    optimal_latency_s: float  # NaN if no path exists in the true graph
    reachable: bool
    misrouted: bool


def compute_metrics(
    packets,
    per_step_route_divergence_frac: np.ndarray,
    per_step_converged: np.ndarray,
    per_step_rounds_to_converge: np.ndarray,
) -> dict:
    """From the packet log and per-step convergence stats, compute the
    exact metrics keys required by SPEC.md §5.5."""
    packets_sent = len(packets)
    delivered = [p for p in packets if p.status is PacketStatus.DELIVERED]
    packets_delivered = len(delivered)
    reachable = [p for p in packets if p.reachable]
    num_reachable = len(reachable)
    misrouted = [p for p in reachable if p.misrouted]

    delivery_ratio = packets_delivered / packets_sent if packets_sent else float("nan")
    delivery_ratio_reachable = (
        packets_delivered / num_reachable if num_reachable else float("nan")
    )
    mean_latency_s = (
        float(np.mean([p.latency_s for p in delivered])) if delivered else float("nan")
    )
    mean_hops = float(np.mean([p.hops for p in delivered])) if delivered else float("nan")
    misrouted_frac = len(misrouted) / num_reachable if num_reachable else float("nan")
    unreachable_frac = (
        (packets_sent - num_reachable) / packets_sent if packets_sent else float("nan")
    )

    route_divergence_frac = (
        float(np.mean(per_step_route_divergence_frac))
        if len(per_step_route_divergence_frac)
        else float("nan")
    )

    valid_converged = per_step_converged[~np.isnan(per_step_converged)]
    valid_rounds = per_step_rounds_to_converge[~np.isnan(per_step_rounds_to_converge)]
    if valid_converged.size:
        converged_step_frac = float(np.mean(valid_converged))
        mean_rounds_to_converge = float(np.mean(valid_rounds))
    else:
        converged_step_frac = float("nan")
        mean_rounds_to_converge = float("nan")

    return {
        "packets_sent": float(packets_sent),
        "packets_delivered": float(packets_delivered),
        "delivery_ratio": delivery_ratio,
        "delivery_ratio_reachable": delivery_ratio_reachable,
        "mean_latency_s": mean_latency_s,
        "mean_hops": mean_hops,
        "misrouted_frac": misrouted_frac,
        "unreachable_frac": unreachable_frac,
        "route_divergence_frac": route_divergence_frac,
        "converged_step_frac": converged_step_frac,
        "mean_rounds_to_converge": mean_rounds_to_converge,
    }
