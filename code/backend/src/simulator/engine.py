"""Current-state vs proposed-state simulation using QuantumReady OS.

The simulator is view-only.

It never modifies the live/current topology. Instead, it creates a deep copy
representing a hypothetical proposed state, applies a scenario to that copy,
and evaluates both states using the same QROS scoring engine.

The simulator also exposes dependency information so the UI can show which
other applications/systems may need to be considered when a selected system
changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from qros.models import KeyManagementType, Topology
from qros.rubric import Rubric
from qros.scoring import AssessmentResult, assess

from .relationships import find_related_nodes


@dataclass(frozen=True)
class SimulationResult:
    """Result of one hypothetical simulator scenario."""

    scenario: str
    node_id: str

    # Direct systems connected to the selected node.
    direct_related_node_ids: tuple[str, ...]

    # All reachable systems in the dependency graph.
    all_related_node_ids: tuple[str, ...]

    current: AssessmentResult
    proposed: AssessmentResult

    # Hypothetical copy only.
    proposed_topology: Topology

    @property
    def score_delta(self) -> float:
        """Difference between proposed and current readiness score."""

        return round(
            self.proposed.composite_score
            - self.current.composite_score,
            1,
        )

    @property
    def failing_findings_delta(self) -> int:
        """Difference in number of failing findings."""

        return (
            len(self.proposed.failing_findings())
            - len(self.current.failing_findings())
        )

    @property
    def direct_impact_count(self) -> int:
        return len(self.direct_related_node_ids)

    @property
    def total_impact_count(self) -> int:
        return len(self.all_related_node_ids)


def find_node(
    topology: Topology,
    node_id: str,
):
    """Find one node in the topology."""

    node = next(
        (
            node
            for node in topology.nodes
            if node.id == node_id
        ),
        None,
    )

    if node is None:
        raise ValueError(
            f"Unknown node_id: {node_id}"
        )

    return node


def apply_pqc_hardening(node) -> None:
    """Apply the proof-of-concept PQC hardening scenario.

    The change is applied only to the hypothetical topology copy.

    Changes currently represented by the QROS v1 schema/rubric:

    - TLS 1.3
    - hybrid X25519 + ML-KEM-768 key exchange
    - PQC-capable crypto library
    - KMS key management
    - <= 90 day key rotation
    - crypto agility
    - documented PQC migration plan
    """

    # ---------------------------------------------------------
    # Network
    # ---------------------------------------------------------

    for protocol in node.network.protocols:

        if protocol.name.lower() == "tls":

            protocol.version = "1.3"

            has_ml_kem = any(
                "ML-KEM" in item.upper()
                for item in protocol.key_exchange
            )

            if not has_ml_kem:
                protocol.key_exchange = [
                    "X25519",
                    "ML-KEM-768",
                ]

    # ---------------------------------------------------------
    # Compute
    # ---------------------------------------------------------

    for library in node.compute.crypto_libraries:
        library.pqc_capable = True

    # ---------------------------------------------------------
    # Security
    # ---------------------------------------------------------

    node.security.key_management.type = (
        KeyManagementType.kms
    )

    node.security.key_management.rotation_policy_days = 90

    node.security.crypto_agility = True

    # ---------------------------------------------------------
    # Governance
    # ---------------------------------------------------------

    node.governance.pqc_migration_plan = True



def run_simulation(
    topology: Topology,
    rubric: Rubric,
    node_id: str,
    scenario: str,
    apply_change: Callable,
) -> SimulationResult:
    """Run a hypothetical simulation using the QROS scoring engine.

    The original topology remains unchanged.
    """

    # Validate the selected node.
    find_node(topology, node_id)

    # Assess the current topology.
    current = assess(topology, rubric)

    # Find potentially related systems.
    direct_related = find_related_nodes(
        topology,
        node_id,
        recursive=False,
    )

    all_related = find_related_nodes(
        topology,
        node_id,
        recursive=True,
    )

    # Create a separate hypothetical topology.
    proposed_topology = topology.model_copy(deep=True)

    # Apply changes only to the copied node.
    target = find_node(proposed_topology, node_id)
    apply_change(target)

    # Assess the hypothetical topology.
    proposed = assess(proposed_topology, rubric)

    return SimulationResult(
        scenario=scenario,
        node_id=node_id,
        direct_related_node_ids=direct_related,
        all_related_node_ids=all_related,
        current=current,
        proposed=proposed,
        proposed_topology=proposed_topology,
    )


def simulate_pqc_hardening(
    topology: Topology,
    rubric: Rubric,
    node_id: str,
) -> SimulationResult:
    """Run the existing PQC-hardening scenario."""

    return run_simulation(
        topology=topology,
        rubric=rubric,
        node_id=node_id,
        scenario="pqc-hardening",
        apply_change=apply_pqc_hardening,
    )
