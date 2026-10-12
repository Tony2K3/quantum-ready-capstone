"""
Tests for the LLM caller internals.
"""

import json
from datetime import datetime

import pytest

from src.roadmap.llm.caller import LLMValidationError, RoadmapCaller
from src.roadmap.models.priority import ApplicationPriority
from src.roadmap.models.roadmap import LLMRoadmapContent, RoadmapOutput

# Helpers

def make_caller() -> RoadmapCaller:
    """Instantiate a caller with a dummy API key. No API calls are made."""
    return RoadmapCaller(api_key="test-key-does-not-call-api")


def make_priority(**overrides) -> ApplicationPriority:
    defaults = {
        "application_id": "APP-001",
        "application_name": "Payment Service",
        "priority_level": "High",
        "priority_score": 72.5,
        "key_factors": ["APP-001.business_criticality = High"],
    }
    defaults.update(overrides)
    return ApplicationPriority(**defaults)


def make_llm_content(**overrides) -> LLMRoadmapContent:
    defaults = {
        "summary": "This is a test roadmap summary.",
        "thirty_day_actions": [],
        "sixty_day_actions": [],
        "ninety_day_actions": [],
        "long_term_roadmap": [],
        "assumptions": [],
        "missing_data": [],
    }
    defaults.update(overrides)
    return LLMRoadmapContent(**defaults)


VALID_CONTENT_DICT = {
    "summary": "Test summary.",
    "thirty_day_actions": [],
    "sixty_day_actions": [],
    "ninety_day_actions": [],
    "long_term_roadmap": [],
    "assumptions": [],
    "missing_data": [],
}


# _extract_json()

class TestExtractJson:

    def test_plain_json_returned_as_is(self):
        text = '{"summary": "hello"}'
        result = RoadmapCaller._extract_json(text)
        assert result == '{"summary": "hello"}'

    def test_leading_trailing_whitespace_stripped(self):
        text = '  \n{"summary": "hello"}\n  '
        result = RoadmapCaller._extract_json(text)
        assert json.loads(result) == {"summary": "hello"}

    def test_markdown_code_block_extracted(self):
        text = '```\n{"summary": "hello"}\n```'
        result = RoadmapCaller._extract_json(text)
        assert json.loads(result) == {"summary": "hello"}

    def test_markdown_json_code_block_extracted(self):
        text = '```json\n{"summary": "hello"}\n```'
        result = RoadmapCaller._extract_json(text)
        assert json.loads(result) == {"summary": "hello"}

    def test_multiline_json_in_code_block_extracted(self):
        text = '```json\n{\n  "summary": "hello",\n  "count": 1\n}\n```'
        result = RoadmapCaller._extract_json(text)
        parsed = json.loads(result)
        assert parsed["summary"] == "hello"
        assert parsed["count"] == 1

    def test_nested_json_extracted_correctly(self):
        """Ensure the outermost object is returned, not an inner one."""
        text = '{"outer": {"inner": "value"}, "other": 1}'
        result = RoadmapCaller._extract_json(text)
        parsed = json.loads(result)
        assert "outer" in parsed
        assert "other" in parsed


# _parse_and_validate()

class TestParseAndValidate:

    def test_valid_json_returns_llm_roadmap_content(self):
        caller = make_caller()
        raw = json.dumps(VALID_CONTENT_DICT)
        result = caller._parse_and_validate(raw)
        assert isinstance(result, LLMRoadmapContent)
        assert result.summary == "Test summary."

    def test_valid_json_in_code_block_passes(self):
        caller = make_caller()
        raw = f"```json\n{json.dumps(VALID_CONTENT_DICT)}\n```"
        result = caller._parse_and_validate(raw)
        assert isinstance(result, LLMRoadmapContent)

    def test_invalid_json_raises_llm_validation_error(self):
        caller = make_caller()
        with pytest.raises(LLMValidationError, match="not valid JSON"):
            caller._parse_and_validate("this is not json at all")

    def test_missing_required_field_raises_llm_validation_error(self):
        caller = make_caller()
        incomplete = {k: v for k, v in VALID_CONTENT_DICT.items() if k != "summary"}
        with pytest.raises(LLMValidationError, match="schema validation"):
            caller._parse_and_validate(json.dumps(incomplete))

    def test_extra_field_raises_llm_validation_error(self):
        """LLMRoadmapContent has extra='forbid' so unexpected fields should fail."""
        caller = make_caller()
        invalid = {**VALID_CONTENT_DICT, "unexpected_field": "value"}
        with pytest.raises(LLMValidationError, match="schema validation"):
            caller._parse_and_validate(json.dumps(invalid))

    def test_wrong_type_raises_llm_validation_error(self):
        caller = make_caller()
        invalid = {**VALID_CONTENT_DICT, "summary": 12345}
        with pytest.raises(LLMValidationError):
            caller._parse_and_validate(json.dumps(invalid))

    def test_empty_json_object_raises_llm_validation_error(self):
        caller = make_caller()
        with pytest.raises(LLMValidationError):
            caller._parse_and_validate("{}")


# _assemble_output()

class TestAssembleOutput:

    def test_returns_roadmap_output(self):
        caller = make_caller()
        result = caller._assemble_output(
            llm_content=make_llm_content(),
            priorities=[make_priority()],
            persona="CISO",
            assessment_version=None,
        )
        assert isinstance(result, RoadmapOutput)

    def test_roadmap_id_starts_with_roadmap(self):
        caller = make_caller()
        result = caller._assemble_output(
            llm_content=make_llm_content(),
            priorities=[],
            persona="EA",
            assessment_version=None,
        )
        assert result.roadmap_id.startswith("ROADMAP-")

    def test_roadmap_id_unique_per_call(self):
        caller = make_caller()
        r1 = caller._assemble_output(make_llm_content(), [], "EA", None)
        r2 = caller._assemble_output(make_llm_content(), [], "EA", None)
        assert r1.roadmap_id != r2.roadmap_id

    def test_persona_preserved(self):
        caller = make_caller()
        result = caller._assemble_output(make_llm_content(), [], "CISO", None)
        assert result.persona == "CISO"

    def test_priorities_preserved(self):
        caller = make_caller()
        priorities = [make_priority(), make_priority(app_id="APP-002", priority_score=50.0)]
        result = caller._assemble_output(make_llm_content(), priorities, "CTO", None)
        assert len(result.priorities) == 2

    def test_summary_from_llm_content(self):
        caller = make_caller()
        content = make_llm_content(summary="Custom summary text.")
        result = caller._assemble_output(content, [], "EA", None)
        assert result.summary == "Custom summary text."

    def test_assessment_version_preserved(self):
        caller = make_caller()
        result = caller._assemble_output(
            make_llm_content(), [], "EA", assessment_version="v2"
        )
        assert result.assessment_version == "v2"

    def test_assessment_version_none_when_not_provided(self):
        caller = make_caller()
        result = caller._assemble_output(make_llm_content(), [], "EA", None)
        assert result.assessment_version is None

    def test_prompt_version_set(self):
        from src.roadmap.llm.prompts import PROMPT_VERSION
        caller = make_caller()
        result = caller._assemble_output(make_llm_content(), [], "EA", None)
        assert result.prompt_version == PROMPT_VERSION

    def test_model_name_set(self):
        caller = make_caller()
        result = caller._assemble_output(make_llm_content(), [], "EA", None)
        assert len(result.model) > 0

    def test_generated_at_is_set(self):
        caller = make_caller()
        result = caller._assemble_output(make_llm_content(), [], "EA", None)
        assert isinstance(result.generated_at, datetime)

    def test_assumptions_from_llm_content(self):
        caller = make_caller()
        content = make_llm_content(assumptions=["Assumed all vendors support PQC by 2026."])
        result = caller._assemble_output(content, [], "EA", None)
        assert result.assumptions == ["Assumed all vendors support PQC by 2026."]

    def test_missing_data_from_llm_content(self):
        caller = make_caller()
        content = make_llm_content(missing_data=["APP-001.crypto_agility"])
        result = caller._assemble_output(content, [], "EA", None)
        assert result.missing_data == ["APP-001.crypto_agility"]
