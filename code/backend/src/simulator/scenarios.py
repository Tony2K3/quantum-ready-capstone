
"""Registry for supported simulation scenarios."""

from collections.abc import Callable

from qros.models import Topology
from qros.rubric import Rubric

from .engine import SimulationResult, simulate_pqc_hardening

ScenarioHandler = Callable[[Topology, Rubric, str], SimulationResult]

SCENARIOS: dict[str, ScenarioHandler] = {
    "pqc-hardening": simulate_pqc_hardening,
}


def list_scenarios() -> list[str]:
    """Return available simulation scenarios."""
    return sorted(SCENARIOS)


def simulate(
    topology: Topology,
    rubric: Rubric,
    scenario: str,
    node_id: str,
) -> SimulationResult:
    """Run the selected simulation scenario."""
    handler = SCENARIOS.get(scenario)

    if handler is None:
        available = ", ".join(list_scenarios())
        raise ValueError(
            f"Unknown scenario '{scenario}'. "
            f"Available scenarios: {available}"
        )

    return handler(topology, rubric, node_id)
