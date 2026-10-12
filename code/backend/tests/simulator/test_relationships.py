
"""M1 tests for simulator dependency analysis."""

from pathlib import Path

import pytest
import yaml
from qros.models import Topology

from src.simulator.relationships import (
    find_related_nodes,
    get_direct_neighbors,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QROS_ROOT = PROJECT_ROOT.parent.parent / "quantumready-os"

TOPOLOGY_PATH = QROS_ROOT / "examples" / "example_topology.yaml"


@pytest.fixture
def topology():
    """Load the QROS example topology."""
    with TOPOLOGY_PATH.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    return Topology.model_validate(data)


# TC11: Direct neighbor detection
def test_direct_neighbors(topology):
    neighbors = get_direct_neighbors(
        topology,
        "edge-gw-01",
    )

    assert "core-cloud-01" in neighbors


# TC12: Reachable node detection
def test_related_nodes(topology):
    related = find_related_nodes(
        topology,
        "edge-gw-01",
    )

    assert "core-cloud-01" in related
    assert "edge-gw-01" not in related
    assert len(related) == 1


# TC13: Selected node should not appear in dependencies
def test_selected_node_excluded(topology):
    related = find_related_nodes(
        topology,
        "edge-gw-01",
    )

    assert "edge-gw-01" not in related


# TC14: No duplicate reachable nodes
def test_no_duplicate_dependencies(topology):
    related = list(
        find_related_nodes(
            topology,
            "edge-gw-01",
        )
    )

    assert len(related) == len(set(related))


# TC15: An isolated node has no dependencies
def test_isolated_node(topology):
    isolated = topology.model_copy(deep=True)

    # Remove connections involving the selected node.
    isolated.connections = [
        connection
        for connection in isolated.connections
        if (
            connection.from_ != "edge-gw-01"
            and connection.to != "edge-gw-01"
        )
    ]

    direct = get_direct_neighbors(
        isolated,
        "edge-gw-01",
    )

    reachable = find_related_nodes(
        isolated,
        "edge-gw-01",
    )

    assert len(direct) == 0
    assert len(reachable) == 0


# TC16: Dependency traversal works from a middle node
def test_middle_node_dependencies(topology):
    related = find_related_nodes(
        topology,
        "core-cloud-01",
    )

    assert "edge-gw-01" in related
    assert "qnode-lab-01" in related


# TC17: Cyclic topology should not cause infinite traversal
def test_cyclic_topology(topology):
    cyclic = topology.model_copy(deep=True)

    # Add a reverse connection to create a cycle.
    connection = cyclic.connections[0].model_copy(deep=True)
    connection.from_ = "core-cloud-01"
    connection.to = "edge-gw-01"

    cyclic.connections.append(connection)

    related = find_related_nodes(
        cyclic,
        "edge-gw-01",
    )

    assert "core-cloud-01" in related
    assert "edge-gw-01" not in related
    assert len(related) == len(set(related))
