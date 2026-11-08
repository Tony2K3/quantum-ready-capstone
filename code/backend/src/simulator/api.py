
"""HTTP API for the Quantinnel simulation engine."""

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError
from qros.models import Topology
from qros.rubric import load_rubric

from .scenarios import list_scenarios, simulate

app = FastAPI(
    title="Quantinnel Simulation API",
    version="0.2.0",
)

DEFAULT_RUBRIC = (
    Path(__file__).resolve().parents[4]
    / "quantumready-os"
    / "qros"
    / "rubric_data"
    / "rubric_v1.yaml"
)


class SimulationRequest(BaseModel):
    scenario: str = "pqc-hardening"
    node_id: str = Field(min_length=1)
    topology: Topology


@lru_cache(maxsize=1)
def get_rubric():
    path = Path(os.environ.get("QROS_RUBRIC_PATH", DEFAULT_RUBRIC))
    return load_rubric(str(path))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "quantinnel-simulator",
    }


@app.get("/api/simulations/scenarios")
def get_scenarios():
    return {"scenarios": list_scenarios()}


@app.post("/api/simulations")
def run_simulation(request: SimulationRequest):
    if request.scenario not in list_scenarios():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario: {request.scenario}",
        )

    try:
        result = simulate(
            topology=request.topology,
            rubric=get_rubric(),
            scenario=request.scenario,
            node_id=request.node_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OSError, ValidationError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Simulation configuration error",
        ) from exc

    return {
        "scenario": result.scenario,
        "node_id": result.node_id,
        "current_score": result.current.composite_score,
        "proposed_score": result.proposed.composite_score,
        "score_delta": result.score_delta,
        "current_failing_findings": len(
            result.current.failing_findings()
        ),
        "proposed_failing_findings": len(
            result.proposed.failing_findings()
        ),
        "failing_findings_delta": result.failing_findings_delta,
        "current_pillars": {
            name: pillar.score
            for name, pillar in result.current.pillars.items()
        },
        "proposed_pillars": {
            name: pillar.score
            for name, pillar in result.proposed.pillars.items()
        },
        "current_critical_cap_applied": (
            result.current.critical_cap_applied
        ),
        "proposed_critical_cap_applied": (
            result.proposed.critical_cap_applied
        ),
        "direct_related_node_ids": result.direct_related_node_ids,
        "all_related_node_ids": result.all_related_node_ids,
    }
