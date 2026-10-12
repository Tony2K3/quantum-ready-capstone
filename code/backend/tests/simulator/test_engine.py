
"""M1 tests for the Integration Simulator engine."""

from pathlib import Path

import pytest
import yaml
from qros.models import Topology
from qros.rubric import Rubric
from qros.scoring import assess

from src.simulator.engine import run_simulation, simulate_pqc_hardening

# Repository paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QROS_ROOT = PROJECT_ROOT.parent.parent / "quantumready-os"

TOPOLOGY_PATH = QROS_ROOT / "examples" / "example_topology.yaml"
RUBRIC_PATH = QROS_ROOT / "qros" / "rubric_data" / "rubric_v1.yaml"


@pytest.fixture
def topology():
    """Load the actual QROS example topology."""
    with TOPOLOGY_PATH.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    return Topology.model_validate(data)


@pytest.fixture
def rubric():
    """Load the actual QROS scoring rubric."""
    with RUBRIC_PATH.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    return Rubric.model_validate(data)


@pytest.fixture
def simulation(topology, rubric):
    """Run a real PQC-hardening simulation."""
    return simulate_pqc_hardening(
        topology,
        rubric,
        "edge-gw-01",
    )


def get_node(topology, node_id):
    """Find a node in the topology."""
    return next(
        node for node in topology.nodes
        if node.id == node_id
    )


# TC01: Valid simulation
def test_valid_simulation(simulation):
    assert simulation.node_id == "edge-gw-01"
    assert simulation.current is not None
    assert simulation.proposed is not None
    assert simulation.proposed_topology is not None


# TC02: Invalid node
def test_invalid_node(topology, rubric):
    with pytest.raises(ValueError):
        simulate_pqc_hardening(
            topology,
            rubric,
            "invalid-node",
        )


# TC03: Original topology must remain unchanged
def test_original_topology_unchanged(topology, rubric):
    original = topology.model_dump(mode="json")

    simulate_pqc_hardening(
        topology,
        rubric,
        "edge-gw-01",
    )

    assert topology.model_dump(mode="json") == original


# TC04: Proposed topology must be a deep copy
def test_proposed_topology_is_separate(simulation, topology):
    assert simulation.proposed_topology is not topology
    assert simulation.proposed_topology.nodes is not topology.nodes

    original_node = get_node(topology, "edge-gw-01")
    proposed_node = get_node(
        simulation.proposed_topology,
        "edge-gw-01",
    )

    assert proposed_node is not original_node


# TC05: PQC-hardening changes are applied
def test_pqc_hardening_updates(simulation):
    node = get_node(
        simulation.proposed_topology,
        "edge-gw-01",
    )

    assert node.security.crypto_agility is True
    assert node.governance.pqc_migration_plan is True
    assert node.security.key_management.rotation_policy_days == 90


# TC06: Proposed readiness score improves
def test_score_improvement(simulation):
    assert (
        simulation.proposed.composite_score
        > simulation.current.composite_score
    )

    assert simulation.score_delta > 0


# TC07: Failing findings decrease
def test_findings_decrease(simulation):
    assert simulation.failing_findings_delta < 0


# TC08: Current assessment matches QROS
def test_current_assessment_uses_qros(topology, rubric, simulation):
    expected = assess(topology, rubric)

    assert simulation.current.composite_score == pytest.approx(
        expected.composite_score
    )


# TC09: Proposed assessment matches QROS
def test_proposed_assessment_uses_qros(rubric, simulation):
    expected = assess(
        simulation.proposed_topology,
        rubric,
    )

    assert simulation.proposed.composite_score == pytest.approx(
        expected.composite_score
    )


# TC10: Score delta is calculated correctly
def test_score_delta_calculation(simulation):
    expected_delta = (
        simulation.proposed.composite_score
        - simulation.current.composite_score
    )

    assert simulation.score_delta == pytest.approx(expected_delta)



# TC11: Reusable engine executes a custom simulation scenario
def test_reusable_engine_dispatch(topology, rubric):
    called = []

    def custom_change(node):
        called.append(node.id)

    result = run_simulation(
        topology=topology,
        rubric=rubric,
        node_id="edge-gw-01",
        scenario="custom-test",
        apply_change=custom_change,
    )

    assert called == ["edge-gw-01"]
    assert result.scenario == "custom-test"
    assert result.score_delta == 0


# TC12: Reusable engine preserves the original topology
def test_reusable_engine_preserves_original(topology, rubric):
    original = topology.model_copy(deep=True)

    def custom_change(node):
        node.security.crypto_agility = True

    run_simulation(
        topology=topology,
        rubric=rubric,
        node_id="edge-gw-01",
        scenario="custom-test",
        apply_change=custom_change,
    )

    assert topology == original
