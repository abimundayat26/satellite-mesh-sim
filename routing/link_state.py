"""
Approach B -- distributed link-state routing (Phase 4).

Each node starts knowing only its direct neighbors. Nodes exchange
routing info with neighbors over a bounded number of rounds
(config.max_convergence_rounds) after each topology change, before
that timestep's routing decision is locked in.

This is where the interesting behavior lives: track how far B's
decisions diverge from A's, and how many rounds convergence actually
takes.
"""


class LinkStateRouter:
    def __init__(self, config):
        self.config = config
        # TODO: per-node routing table state

    def on_topology_change(self, adjacency):
        """TODO: kick off a new convergence process."""
        raise NotImplementedError

    def step_round(self):
        """
        TODO: one round of neighbor info exchange. Call this up to
        config.max_convergence_rounds times per topology change.
        """
        raise NotImplementedError

    def routing_table(self, node) -> dict:
        """TODO: return this node's current {destination: next_hop}."""
        raise NotImplementedError
