"""
Jev scoring integration for the Decision Cortex roadmap generator.

Calls the Jev (TypeSafe AI) System One model to score each application
across five independent quantum-readiness dimensions. Results are mapped
to ApplicationPriority objects for downstream LLM context assembly.

Two connectors are provided:
  JevClient.from_n8n()          — n8n webhook (temporary)
  JevClient.from_airflow(url)   — direct Jev URL via Apache Airflow (production)

Jev evaluates all five questions in a single parallel call per application.
Applications are scored concurrently using a thread pool.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from ..models.application import Application
from ..models.enterprise_architecture import EnterpriseArchitecture
from ..models.priority import ApplicationPriority, PriorityLevel

# Jev question definitions

JEV_QUESTIONS: dict = {
    "quantum_vulnerability": {
        "type": "score",
        "instructions": (
            "How vulnerable is this application's current cryptographic setup "
            "to quantum attacks, considering its protocols, algorithms, key "
            "management, and PQC readiness state?"
        ),
        "criteria": [
            "Modern or PQC-capable cryptography already in place or actively in progress",
            "Standard classical cryptography — not immediately vulnerable but not quantum-ready",
            "Weak or outdated cryptographic setup with significant quantum exposure",
        ],
    },
    "data_exposure_risk": {
        "type": "score",
        "instructions": (
            "How exposed is this application's data to harvest-now-decrypt-later "
            "(HNDL) attacks, where an adversary captures encrypted data today to "
            "decrypt once quantum computers are available?"
        ),
        "criteria": [
            "Minimal — non-sensitive data or very short retention period",
            "Moderate — sensitive data with medium retention period",
            "High — highly sensitive data with long retention, HNDL is a realistic threat",
        ],
    },
    "business_impact": {
        "type": "score",
        "instructions": (
            "How severe would the business impact be if this application's "
            "cryptography was compromised by a quantum attack?"
        ),
        "criteria": [
            "Low — non-critical application, limited downstream consequences",
            "Moderate — important application with some downstream business impact",
            "Severe — critical application, compromise would have major business consequences",
        ],
    },
    "migration_complexity": {
        "type": "score",
        "instructions": (
            "How complex would it be to migrate this application to "
            "post-quantum cryptography, considering its crypto agility, "
            "vendor dependencies, and technical stack?"
        ),
        "criteria": [
            "Straightforward — crypto-agile, modern stack, low vendor dependency",
            "Moderate — some rework needed, possible vendor coordination required",
            "Complex — not crypto-agile, legacy stack, high vendor dependency",
        ],
    },
    "dependency_risk": {
        "type": "score",
        "instructions": (
            "How much would migrating this application to PQC disrupt other "
            "applications that depend on it?"
        ),
        "criteria": [
            "Isolated — few or no other applications depend on this one",
            "Moderate — some applications depend on this one, migration needs coordination",
            "High — many critical applications depend on this one, sequencing is essential",
        ],
    },
}

# Max score value for each question (number of criteria levels - 1)
_MAX_SCORES: dict[str, float] = {q: float(len(v["criteria"]) - 1) for q, v in JEV_QUESTIONS.items()}

# Weights for combining scores into a single priority_score (must sum to 1.0)
_WEIGHTS: dict[str, float] = {
    "quantum_vulnerability": 0.25,
    "data_exposure_risk":    0.25,
    "business_impact":       0.25,
    "migration_complexity":  0.15,
    "dependency_risk":       0.10,
}

# Priority level thresholds (priority_score is 0-100)
_THRESHOLDS: list[tuple[float, PriorityLevel]] = [
    (75.0, "Critical"),
    (55.0, "High"),
    (35.0, "Medium"),
    (0.0,  "Low"),
]

# Fields checked for missing data
_TRACKED_FIELDS = [
    "business_criticality",
    "data_sensitivity",
    "data_longevity",
    "vendor_dependency",
    "owner",
    "network_exposure",
    "network_protocols",
    "crypto_agility",
    "key_management_type",
    "cryptographic_dependencies",
]


# JevClient

class JevClient:
    """
    HTTP client for the Jev System One model.

    Use JevClient.from_n8n() for testing via the n8n webhook.
    Use JevClient.from_airflow(url) for production via Apache Airflow.
    """

    _N8N_URL_ENV_VAR = "JEV_N8N_URL"

    def __init__(self, url: str, timeout: int = 30) -> None:
        self._url = url
        self._timeout = timeout

    @classmethod
    def from_n8n(cls) -> JevClient:
        """n8n webhook — temporary testing solution.
        Reads the URL from the JEV_N8N_URL environment variable.
        """
        url = os.environ.get(cls._N8N_URL_ENV_VAR)
        if not url:
            raise ValueError(
                f"Environment variable '{cls._N8N_URL_ENV_VAR}' is not set. "
                "Set it to the n8n webhook URL before calling from_n8n()."
            )
        return cls(url=url)

    @classmethod
    def from_airflow(cls, url: str) -> JevClient:
        """Direct Jev endpoint via Apache Airflow — production solution."""
        return cls(url=url)

    def ask(self, state: dict, questions: dict) -> dict:
        """
        Send a state and typed questions to Jev.
        Returns the answers dict keyed by question ID.
        """
        resp = requests.post(
            self._url,
            json={"state": state, "questions": questions},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["answers"]


# state builder

def _build_state(
    app: Application,
    architecture: EnterpriseArchitecture,
) -> dict:
    """Build the Jev state for a single application, including connection context."""
    app_lookup = {a.id: a.name for a in architecture.applications}

    depends_on = [
        {
            "application": app_lookup.get(c.target_application_id, c.target_application_id),
            "relationship": c.relationship,
            "dependency_type": c.dependency_type,
        }
        for c in architecture.connections
        if c.source_application_id == app.id
    ]

    depended_on_by = [
        {
            "application": app_lookup.get(c.source_application_id, c.source_application_id),
            "relationship": c.relationship,
            "dependency_type": c.dependency_type,
        }
        for c in architecture.connections
        if c.target_application_id == app.id
    ]

    return {
        "id": app.id,
        "name": app.name,
        "business_criticality": app.business_criticality,
        "data_sensitivity": app.data_sensitivity,
        "data_longevity": app.data_longevity,
        "vendor_dependency": app.vendor_dependency,
        "owner": app.owner,
        "deployment_environment": app.deployment_environment,
        "network_exposure": app.network_exposure,
        "network_protocols": app.network_protocols,
        "crypto_agility": app.crypto_agility,
        "key_management_type": app.key_management_type,
        "cryptographic_dependencies": app.cryptographic_dependencies,
        "pqc_readiness": app.pqc_readiness,
        "depends_on": depends_on,
        "depended_on_by": depended_on_by,
    }


# Mapping helpers

def _priority_score(answers: dict) -> float:
    """Compute a 0-100 priority score from Jev's dimension scores."""
    return sum(
        (answers[q]["score"] / _MAX_SCORES[q]) * weight
        for q, weight in _WEIGHTS.items()
        if q in answers
    ) * 100.0


def _priority_level(score: float) -> PriorityLevel:
    for threshold, level in _THRESHOLDS:
        if score >= threshold:
            return level
    return "Low"


def _build_key_factors(app_id: str, answers: dict) -> list[str]:
    """
    Build key_factors from Jev's scores.
    Only includes dimensions that scored above their midpoint.
    Uses the criteria text for the nearest level as the description.
    """
    factors = []
    for question, answer in answers.items():
        score = answer["score"]
        max_score = _MAX_SCORES[question]
        if score > max_score / 2:
            criteria = JEV_QUESTIONS[question]["criteria"]
            level_idx = min(round(score), len(criteria) - 1)
            factors.append(
                f"{app_id}.{question} = {score:.1f}/{max_score:.0f} "
                f"— {criteria[level_idx]}"
            )
    return factors


def _detect_missing_fields(app: Application) -> list[str]:
    """Return field references for any Application fields that are None."""
    return [
        f"{app.id}.{field}"
        for field in _TRACKED_FIELDS
        if getattr(app, field) is None
    ]


# Per-application scoring

def _score_application(
    app: Application,
    architecture: EnterpriseArchitecture,
    client: JevClient,
) -> ApplicationPriority:
    """Score a single application via Jev and return an ApplicationPriority."""
    state = _build_state(app, architecture)
    answers = client.ask(state, JEV_QUESTIONS)

    score = _priority_score(answers)
    return ApplicationPriority(
        application_id=app.id,
        application_name=app.name,
        priority_level=_priority_level(score),
        priority_score=round(score, 1),
        key_factors=_build_key_factors(app.id, answers),
        missing_fields=_detect_missing_fields(app),
    )


# Public API

def score_applications(
    architecture: EnterpriseArchitecture,
    client: JevClient,
    max_workers: int = 10,
) -> list[ApplicationPriority]:
    """
    Score all applications in the architecture via Jev.

    Applications are scored concurrently. Results are returned sorted
    highest priority first.

    Args:
        architecture: The validated enterprise architecture input.
        client:       JevClient instance (from_n8n or from_airflow).
        max_workers:  Max concurrent Jev calls. Default 10.

    Returns:
        Sorted list of ApplicationPriority, highest priority_score first.
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_score_application, app, architecture, client): app
            for app in architecture.applications
        }
        priorities = [future.result() for future in as_completed(futures)]

    return sorted(priorities, key=lambda p: p.priority_score, reverse=True)
