"""
Shared routing interface. Approach A (routing/centralized.py) and
Approach B (routing/link_state.py) both implement this protocol.
"""
from typing import Protocol

import numpy as np

from link.visibility import LinkGraph


class Router(Protocol):
    def update(self, graph: LinkGraph) -> None: ...

    def next_hop_table(self) -> np.ndarray: ...

    def kill(self, node_id: int) -> None: ...
