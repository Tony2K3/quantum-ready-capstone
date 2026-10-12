"""
Tests for LLM prompt building and context assembly.

Covers build_system_prompt() in llm/prompts.py and
assemble_prompt() in llm/context.py.
"""

import pytest

from src.roadmap.llm.context import assemble_prompt
from src.roadmap.llm.prompts import PERSONAS, PROMPT_VERSION, build_system_prompt
from src.roadmap.models.application import Application
from src.roadmap.models.connection import Connection
from src.roadmap.models.enterprise_architecture import EnterpriseArchitecture
from src.roadmap.models.priority import ApplicationPriority

# Helpers

def make_priority(
    app_id: str = "APP-001",
    app_name: str = "Payment Service",
    priority_level: str = "Critical",
    priority_score: float = 85.0,
    key_factors: list[str] | None = None,
    missing_fields: list[str] | None = None,
    critical_check_failures: list[str] | None = None,
) -> ApplicationPriority:
    return ApplicationPriority(
        application_id=app_id,
        application_name=app_name,
        priority_level=priority_level,
        priority_score=priority_score,
        key_factors=key_factors or ["APP-001.business_criticality = High"],
        missing_fields=missing_fields or [],
        critical_check_failures=critical_check_failures or [],
    )


def make_architecture(
    app_ids: list[str] | None = None,
    connections: list[Connection] | None = None,
) -> EnterpriseArchitecture:
    ids = app_ids or ["APP-001"]
    apps = [
        Application(id=app_id, name=f"App {app_id}")
        for app_id in ids
    ]
    return EnterpriseArchitecture(
        applications=apps,
        connections=connections or [],
    )


DUMMY_SCHEMA = '{"type": "object"}'


# build_system_prompt()

class TestBuildSystemPrompt:

    def test_valid_ea_persona(self):
        prompt = build_system_prompt("EA", DUMMY_SCHEMA)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_valid_cto_persona(self):
        prompt = build_system_prompt("CTO", DUMMY_SCHEMA)
        assert isinstance(prompt, str)

    def test_valid_ciso_persona(self):
        prompt = build_system_prompt("CISO", DUMMY_SCHEMA)
        assert isinstance(prompt, str)

    def test_invalid_persona_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid persona"):
            build_system_prompt("PM", DUMMY_SCHEMA)

    def test_invalid_persona_error_lists_valid_options(self):
        with pytest.raises(ValueError, match="EA"):
            build_system_prompt("INVALID", DUMMY_SCHEMA)

    def test_output_schema_included_in_prompt(self):
        schema = '{"title": "LLMRoadmapContent"}'
        prompt = build_system_prompt("EA", schema)
        assert schema in prompt

    def test_prompt_version_constant_exists(self):
        assert isinstance(PROMPT_VERSION, str)
        assert len(PROMPT_VERSION) > 0

    def test_different_personas_produce_different_prompts(self):
        ea = build_system_prompt("EA", DUMMY_SCHEMA)
        cto = build_system_prompt("CTO", DUMMY_SCHEMA)
        ciso = build_system_prompt("CISO", DUMMY_SCHEMA)
        assert ea != cto
        assert ea != ciso
        assert cto != ciso

    def test_ea_prompt_mentions_architecture(self):
        prompt = build_system_prompt("EA", DUMMY_SCHEMA)
        assert "architect" in prompt.lower()

    def test_cto_prompt_mentions_business_or_investment(self):
        prompt = build_system_prompt("CTO", DUMMY_SCHEMA)
        assert any(word in prompt.lower() for word in ("business", "investment", "strategic"))

    def test_ciso_prompt_mentions_security_or_risk(self):
        prompt = build_system_prompt("CISO", DUMMY_SCHEMA)
        assert any(word in prompt.lower() for word in ("security", "risk", "cryptograph"))

    def test_hard_rules_present_in_all_prompts(self):
        for persona in PERSONAS:
            prompt = build_system_prompt(persona, DUMMY_SCHEMA)
            assert "do not" in prompt.lower() or "must not" in prompt.lower() or "never" in prompt.lower()

    def test_all_personas_defined(self):
        assert "EA" in PERSONAS
        assert "CTO" in PERSONAS
        assert "CISO" in PERSONAS


# assemble_prompt()

class TestAssemblePrompt:

    def test_returns_prompt_payload(self):
        priorities = [make_priority()]
        arch = make_architecture()
        payload = assemble_prompt(priorities, arch, "CISO")
        assert hasattr(payload, "system_prompt")
        assert hasattr(payload, "user_message")
        assert hasattr(payload, "prompt_version")

    def test_prompt_version_matches_constant(self):
        payload = assemble_prompt([make_priority()], make_architecture(), "EA")
        assert payload.prompt_version == PROMPT_VERSION

    def test_application_name_in_user_message(self):
        priority = make_priority(app_name="Payment Service")
        arch = make_architecture(["APP-001"])
        payload = assemble_prompt([priority], arch, "EA")
        assert "Payment Service" in payload.user_message

    def test_applications_sorted_highest_priority_first(self):
        low = make_priority(app_id="APP-001", app_name="Low App", priority_score=20.0)
        high = make_priority(app_id="APP-002", app_name="High App", priority_score=90.0)
        arch = make_architecture(["APP-001", "APP-002"])
        payload = assemble_prompt([low, high], arch, "CTO")
        low_pos = payload.user_message.index("Low App")
        high_pos = payload.user_message.index("High App")
        assert high_pos < low_pos

    def test_dependencies_appear_in_user_message(self):
        arch = make_architecture(
            app_ids=["APP-001", "APP-002"],
            connections=[
                Connection(
                    source_application_id="APP-001",
                    target_application_id="APP-002",
                    relationship="API",
                )
            ],
        )
        priorities = [
            make_priority(app_id="APP-001"),
            make_priority(app_id="APP-002", app_name="Target App", priority_score=50.0),
        ]
        payload = assemble_prompt(priorities, arch, "EA")
        assert "APP-001" in payload.user_message
        assert "APP-002" in payload.user_message

    def test_missing_fields_appear_in_user_message(self):
        priority = make_priority(
            missing_fields=["business_criticality", "data_longevity"]
        )
        arch = make_architecture()
        payload = assemble_prompt([priority], arch, "CISO")
        assert "business_criticality" in payload.user_message
        assert "data_longevity" in payload.user_message

    def test_critical_check_failures_appear_in_user_message(self):
        priority = make_priority(critical_check_failures=["NET-003"])
        arch = make_architecture()
        payload = assemble_prompt([priority], arch, "CISO")
        assert "NET-003" in payload.user_message

    def test_different_personas_produce_different_system_prompts(self):
        priorities = [make_priority()]
        arch = make_architecture()
        ea = assemble_prompt(priorities, arch, "EA")
        ciso = assemble_prompt(priorities, arch, "CISO")
        assert ea.system_prompt != ciso.system_prompt

    def test_same_persona_same_user_message_content(self):
        priorities = [make_priority()]
        arch = make_architecture()
        p1 = assemble_prompt(priorities, arch, "CTO")
        p2 = assemble_prompt(priorities, arch, "CTO")
        assert p1.user_message == p2.user_message

    def test_organisation_name_in_user_message(self):
        priorities = [make_priority()]
        arch = make_architecture()
        payload = assemble_prompt(priorities, arch, "EA", organization="Acme Corp")
        assert "Acme Corp" in payload.user_message

    def test_invalid_persona_raises(self):
        with pytest.raises(ValueError):
            assemble_prompt([make_priority()], make_architecture(), "PM")
