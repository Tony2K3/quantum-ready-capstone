"""
Tests for Jev scoring integration.

Mocks the HTTP call to the Jev webhook so tests run without
real credentials or network access.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.roadmap.analysis.jev_scoring import (
    JEV_QUESTIONS,
    JevClient,
    _build_key_factors,
    _build_state,
    _detect_missing_fields,
    _priority_level,
    _priority_score,
    score_applications,
)
from src.roadmap.models.application import Application
from src.roadmap.models.connection import Connection
from src.roadmap.models.enterprise_architecture import EnterpriseArchitecture
from src.roadmap.models.priority import ApplicationPriority

# Helpers

def make_application(**overrides) -> Application:
    defaults = {
        "id": "APP-001",
        "name": "Payment Service",
        "business_criticality": "High",
        "data_sensitivity": "High",
        "data_longevity": "Long",
        "vendor_dependency": "High",
        "owner": "Payments Team",
        "network_exposure": "Public",
        "network_protocols": ["TLS 1.2"],
        "crypto_agility": False,
        "key_management_type": "Software",
        "cryptographic_dependencies": ["RSA-2048"],
        "pqc_readiness": "Not Assessed",
    }
    defaults.update(overrides)
    return Application(**defaults)


def make_architecture(*apps, connections=None) -> EnterpriseArchitecture:
    return EnterpriseArchitecture(
        applications=list(apps),
        connections=connections or [],
    )


def make_high_risk_answers() -> dict:
    """Jev answers representing a high-risk application."""
    return {
        "quantum_vulnerability": {"score": 1.9, "confidence": 0.92},
        "data_exposure_risk":    {"score": 2.0, "confidence": 0.96},
        "business_impact":       {"score": 1.8, "confidence": 0.90},
        "migration_complexity":  {"score": 1.7, "confidence": 0.85},
        "dependency_risk":       {"score": 1.2, "confidence": 0.78},
    }


def make_low_risk_answers() -> dict:
    """Jev answers representing a low-risk application."""
    return {
        "quantum_vulnerability": {"score": 0.2, "confidence": 0.88},
        "data_exposure_risk":    {"score": 0.1, "confidence": 0.91},
        "business_impact":       {"score": 0.3, "confidence": 0.85},
        "migration_complexity":  {"score": 0.4, "confidence": 0.80},
        "dependency_risk":       {"score": 0.1, "confidence": 0.90},
    }


def mock_jev_response(answers: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"answers": answers, "model": "jev-1.13.0"}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def make_client() -> JevClient:
    """Create a JevClient with a dummy URL for testing."""
    return JevClient(url="https://test.example.com/jev")


# JevClient

class TestJevClient:

    def test_from_n8n_reads_from_env_var(self):
        with patch.dict("os.environ", {"JEV_N8N_URL": "https://example.n8n.cloud/webhook/jev"}):
            client = JevClient.from_n8n()
            assert client._url == "https://example.n8n.cloud/webhook/jev"

    def test_from_n8n_raises_if_env_var_not_set(self):
        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValueError, match="JEV_N8N_URL"):
            JevClient.from_n8n()

    def test_from_airflow_uses_provided_url(self):
        client = JevClient.from_airflow("https://airflow.example.com/jev")
        assert client._url == "https://airflow.example.com/jev"

    def test_ask_posts_correct_payload(self):
        client = make_client()
        with patch("requests.post", return_value=mock_jev_response(make_high_risk_answers())) as mock_post:
            client.ask({"name": "App"}, JEV_QUESTIONS)
            call_kwargs = mock_post.call_args
            assert call_kwargs.kwargs["json"]["state"] == {"name": "App"}
            assert "quantum_vulnerability" in call_kwargs.kwargs["json"]["questions"]

    def test_ask_returns_answers_dict(self):
        client = make_client()
        answers = make_high_risk_answers()
        with patch("requests.post", return_value=mock_jev_response(answers)):
            result = client.ask({}, JEV_QUESTIONS)
        assert result == answers

    def test_ask_raises_on_http_error(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
        with patch("requests.post", return_value=mock_resp), pytest.raises(Exception, match="HTTP 500"):
            client.ask({}, JEV_QUESTIONS)


# State builder

class TestBuildState:

    def test_includes_application_fields(self):
        app = make_application()
        arch = make_architecture(app)
        state = _build_state(app, arch)
        assert state["id"] == "APP-001"
        assert state["name"] == "Payment Service"
        assert state["business_criticality"] == "High"
        assert state["data_longevity"] == "Long"

    def test_includes_empty_connections_when_none(self):
        app = make_application()
        arch = make_architecture(app)
        state = _build_state(app, arch)
        assert state["depends_on"] == []
        assert state["depended_on_by"] == []

    def test_includes_upstream_dependencies(self):
        app1 = make_application(id="APP-001")
        app2 = make_application(id="APP-002", name="Database")
        conn = Connection(
            source_application_id="APP-001",
            target_application_id="APP-002",
            relationship="Database",
        )
        arch = make_architecture(app1, app2, connections=[conn])
        state = _build_state(app1, arch)
        assert len(state["depends_on"]) == 1
        assert state["depends_on"][0]["application"] == "Database"

    def test_includes_downstream_dependents(self):
        app1 = make_application(id="APP-001")
        app2 = make_application(id="APP-002", name="Customer Portal")
        conn = Connection(
            source_application_id="APP-002",
            target_application_id="APP-001",
            relationship="API",
        )
        arch = make_architecture(app1, app2, connections=[conn])
        state = _build_state(app1, arch)
        assert len(state["depended_on_by"]) == 1
        assert state["depended_on_by"][0]["application"] == "Customer Portal"


# Score mapping

class TestScoreMapping:

    def test_high_risk_answers_produce_high_score(self):
        score = _priority_score(make_high_risk_answers())
        assert score > 70.0

    def test_low_risk_answers_produce_low_score(self):
        score = _priority_score(make_low_risk_answers())
        assert score < 30.0

    def test_priority_level_critical_threshold(self):
        assert _priority_level(80.0) == "Critical"

    def test_priority_level_high_threshold(self):
        assert _priority_level(60.0) == "High"

    def test_priority_level_medium_threshold(self):
        assert _priority_level(40.0) == "Medium"

    def test_priority_level_low_threshold(self):
        assert _priority_level(20.0) == "Low"

    def test_key_factors_included_above_midpoint(self):
        answers = make_high_risk_answers()
        factors = _build_key_factors("APP-001", answers)
        assert len(factors) > 0
        assert all("APP-001." in f for f in factors)

    def test_key_factors_excluded_below_midpoint(self):
        answers = make_low_risk_answers()
        factors = _build_key_factors("APP-001", answers)
        assert len(factors) == 0

    def test_key_factors_include_score_and_criteria_text(self):
        answers = {"quantum_vulnerability": {"score": 1.9, "confidence": 0.92}}
        factors = _build_key_factors("APP-001", answers)
        assert len(factors) == 1
        assert "1.9/2" in factors[0]
        assert "APP-001.quantum_vulnerability" in factors[0]


# Missing fields

class TestDetectMissingFields:

    def test_fully_populated_app_has_no_missing_fields(self):
        app = make_application()
        assert _detect_missing_fields(app) == []

    def test_missing_owner_detected(self):
        app = make_application(owner=None)
        missing = _detect_missing_fields(app)
        assert "APP-001.owner" in missing

    def test_multiple_missing_fields_detected(self):
        app = make_application(
            owner=None,
            crypto_agility=None,
            network_protocols=None,
        )
        missing = _detect_missing_fields(app)
        assert "APP-001.owner" in missing
        assert "APP-001.crypto_agility" in missing
        assert "APP-001.network_protocols" in missing


# score_applications

class TestScoreApplications:

    def test_returns_one_priority_per_application(self):
        apps = [make_application(id=f"APP-00{i}", name=f"App {i}") for i in range(1, 4)]
        arch = make_architecture(*apps)
        client = make_client()
        with patch("requests.post", return_value=mock_jev_response(make_high_risk_answers())):
            priorities = score_applications(arch, client)
        assert len(priorities) == 3

    def test_results_sorted_highest_priority_first(self):
        app1 = make_application(id="APP-001", name="Low Risk App")
        app2 = make_application(id="APP-002", name="High Risk App")
        arch = make_architecture(app1, app2)
        client = make_client()

        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            answers = make_high_risk_answers() if call_count == 1 else make_low_risk_answers()
            return mock_jev_response(answers)

        with patch("requests.post", side_effect=side_effect):
            priorities = score_applications(arch, client)

        assert priorities[0].priority_score >= priorities[1].priority_score

    def test_returns_application_priority_instances(self):
        app = make_application()
        arch = make_architecture(app)
        client = make_client()
        with patch("requests.post", return_value=mock_jev_response(make_high_risk_answers())):
            priorities = score_applications(arch, client)
        assert all(isinstance(p, ApplicationPriority) for p in priorities)
