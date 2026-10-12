"""Relationship and dependency analysis for the integration simulator.

The relationship graph comes directly from the normalized QROS topology.

The simulator does not invent application relationships. It uses
Topology.connections to determine which systems are connected to the
selected application/node.
"""

from __future__ import annotations

from collections import deque

from qros.models import Topology


def validate_node(
    topology: Topology,
    node_id: str,
) -> None:
    """Ensure the requested node exists in the topology."""

    exists = any(
        node.id == node_id
        for node in topology.nodes
    )

    if not exists:
        raise ValueError(
            f"Unknown node_id: {node_id}"
        )


def get_direct_neighbors(
    topology: Topology,
    node_id: str,
) -> tuple[str, ...]:
    """Return systems directly connected to the selected node.

    For impact analysis, both incoming and outgoing connections are
    considered relationships.

    Example:

        A -> B -> C

    Selecting B returns both A and C because a change to B may need
    consideration of systems communicating with B on either side.
    """

    validate_node(
        topology,
        node_id,
    )

    neighbors: set[str] = set()

    for connection in topology.connections:

        source = connection.from_
        target = connection.to

        # Selected node sends data to another system.
        if source == node_id:
            neighbors.add(target)

        # Another system sends data to selected node.
        if target == node_id:
            neighbors.add(source)

    return tuple(
        sorted(neighbors)
    )


def find_related_nodes(
    topology: Topology,
    node_id: str,
    recursive: bool = False,
) -> tuple[str, ...]:
    """Find systems related to the selected application/node.

    Parameters
    ----------
    topology:
        Current QROS topology.

    node_id:
        Application/node selected by the user.

    recursive:
        False:
            Return only directly connected systems.

        True:
            Traverse the complete reachable relationship graph.

    The recursive traversal is cycle-safe.
    """

    validate_node(
        topology,
        node_id,
    )

    # ---------------------------------------------------------
    # Direct relationships only
    # ---------------------------------------------------------

    if not recursive:
        return get_direct_neighbors(
            topology,
            node_id,
        )

    # ---------------------------------------------------------
    # Recursive dependency traversal
    # ---------------------------------------------------------

    visited: set[str] = {node_id}

    related: list[str] = []

    queue = deque(
        get_direct_neighbors(
            topology,
            node_id,
        )
    )

    while queue:

        current = queue.popleft()

        if current in visited:
            continue

        visited.add(current)

        related.append(current)

        neighbors = get_direct_neighbors(
            topology,
            current,
        )

        for neighbor in neighbors:

            if neighbor not in visited:
                queue.append(neighbor)

    return tuple(related)