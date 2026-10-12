"""CLI demo for the QuantumReady integration simulator.

This demo:
- Loads a QROS topology YAML file.
- Loads the QROS scoring rubric.
- Runs a view-only PQC-hardening simulation.
- Displays dependency impact.
- Compares current vs proposed readiness scores.
- Compares failing findings.
- Compares pillar scores.

The original topology is never modified.
"""

from __future__ import annotations

import argparse

import yaml
from qros.models import Topology
from qros.rubric import load_rubric

from .engine import simulate_pqc_hardening


def load_topology(path: str) -> Topology:
    """Load a topology YAML file into the QROS Topology model."""

    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    return Topology.model_validate(data)


def print_simulation(result) -> None:
    """Print a human-readable simulation result."""

    # =========================================================
    # Header
    # =========================================================

    print()
    print("=" * 60)
    print("QUANTUMREADY INTEGRATION SIMULATOR")
    print("=" * 60)

    print()
    print(f"Scenario: {result.scenario}")
    print(f"Selected node: {result.node_id}")

    # =========================================================
    # Dependency impact
    # =========================================================

    print()
    print("DEPENDENCY IMPACT")
    print("-" * 60)

    if result.direct_related_node_ids:
        print(
            f"Directly related systems: "
            f"{result.direct_impact_count}"
        )

        for node_id in result.direct_related_node_ids:
            print(f"  - {node_id}")

    else:
        print(
            "No direct relationship data found "
            "for this node."
        )

    print()

    if result.all_related_node_ids:
        print(
            f"Total reachable systems: "
            f"{result.total_impact_count}"
        )

        for node_id in result.all_related_node_ids:
            print(f"  - {node_id}")

    else:
        print(
            "No additional dependency impact "
            "identified."
        )

    # =========================================================
    # Readiness score comparison
    # =========================================================

    print()
    print("READINESS COMPARISON")
    print("-" * 60)

    current_score = result.current.composite_score
    proposed_score = result.proposed.composite_score

    print(
        f"Current score:  "
        f"{current_score:.1f}"
    )

    print(
        f"Proposed score: "
        f"{proposed_score:.1f}"
    )

    score_sign = "+" if result.score_delta >= 0 else ""

    print(
        f"Score delta:    "
        f"{score_sign}{result.score_delta:.1f}"
    )

    # =========================================================
    # Findings comparison
    # =========================================================

    current_failures = len(
        result.current.failing_findings()
    )

    proposed_failures = len(
        result.proposed.failing_findings()
    )

    print()
    print("FINDINGS")
    print("-" * 60)

    print(
        f"Current failing findings:  "
        f"{current_failures}"
    )

    print(
        f"Proposed failing findings: "
        f"{proposed_failures}"
    )

    print(
        f"Finding delta:             "
        f"{result.failing_findings_delta:+d}"
    )

    # =========================================================
    # Pillar comparison
    # =========================================================

    print()
    print("PILLAR COMPARISON")
    print("-" * 60)

    # AssessmentResult.pillars:
    # dict[str, PillarResult]
    #
    # PillarResult:
    #   score: float
    #   weight: float

    current_pillars = result.current.pillars
    proposed_pillars = result.proposed.pillars

    for pillar_name, current_pillar in current_pillars.items():

        proposed_pillar = proposed_pillars.get(
            pillar_name
        )

        if proposed_pillar is None:
            continue

        current_pillar_score = (
            current_pillar.score
        )

        proposed_pillar_score = (
            proposed_pillar.score
        )

        pillar_delta = (
            proposed_pillar_score
            - current_pillar_score
        )

        print(
            f"{pillar_name:<15}"
            f"{current_pillar_score:>6.1f}"
            f" -> "
            f"{proposed_pillar_score:>6.1f}"
            f"   ({pillar_delta:+.1f})"
        )

    # =========================================================
    # Critical-cap information
    # =========================================================

    print()
    print("CRITICAL CAP")
    print("-" * 60)

    print(
        "Current state:  "
        f"{'YES' if result.current.critical_cap_applied else 'NO'}"
    )

    print(
        "Proposed state: "
        f"{'YES' if result.proposed.critical_cap_applied else 'NO'}"
    )

    # =========================================================
    # Footer
    # =========================================================

    print()
    print("=" * 60)
    print(
        "Simulation only — "
        "the original topology was not modified."
    )
    print("=" * 60)


def main() -> None:
    """Run the simulator CLI."""

    parser = argparse.ArgumentParser(
        description=(
            "Run a QuantumReady current-state "
            "vs proposed-state simulation."
        )
    )

    # ---------------------------------------------------------
    # Topology file
    # ---------------------------------------------------------

    parser.add_argument(
        "topology",
        help=(
            "Path to the QROS topology YAML file."
        ),
    )

    # ---------------------------------------------------------
    # Rubric
    # ---------------------------------------------------------

    parser.add_argument(
        "--rubric",
        required=True,
        help=(
            "Path to the QROS scoring rubric YAML file."
        ),
    )

    # ---------------------------------------------------------
    # Selected node
    # ---------------------------------------------------------

    parser.add_argument(
        "--node",
        required=True,
        help=(
            "Node/application ID to simulate."
        ),
    )

    args = parser.parse_args()

    # =========================================================
    # Load topology
    # =========================================================

    topology = load_topology(
        args.topology
    )

    # =========================================================
    # Load rubric
    # =========================================================

    rubric = load_rubric(
        args.rubric
    )

    # =========================================================
    # Run simulation
    # =========================================================

    result = simulate_pqc_hardening(
        topology=topology,
        rubric=rubric,
        node_id=args.node,
    )

    # =========================================================
    # Display result
    # =========================================================

    print_simulation(
        result
    )


if __name__ == "__main__":
    main()