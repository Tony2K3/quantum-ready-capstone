"""
LLM caller for the Decision Cortex roadmap generator.

Responsibilities:
  1. Send a PromptPayload to the LLM (Anthropic Claude by default)
  2. Extract and parse JSON from the response
  3. Validate the response against LLMRoadmapContent
  4. Retry once on validation failure
  5. Assemble and return the final RoadmapOutput

Provider swapping:
  The LLM call is isolated in _call_llm(). To swap providers, subclass
  RoadmapCaller and override _call_llm() — everything else stays the same.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import anthropic
from pydantic import ValidationError

from ..models.priority import ApplicationPriority
from ..models.roadmap import LLMRoadmapContent, RoadmapOutput
from .context import PromptPayload
from .prompts import PROMPT_VERSION

# Default model — override via RoadmapCaller(model=...) if needed
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_MAX_TOKENS = 16000


class LLMCallError(Exception):
    """Raised when the LLM API call itself fails."""


class LLMValidationError(Exception):
    """Raised when the LLM response cannot be parsed or validated after retry."""


class RoadmapCaller:
    """
    Calls the LLM with a PromptPayload and returns a validated RoadmapOutput.

    Usage:
        caller = RoadmapCaller(api_key="sk-...")
        output = caller.generate(
            payload=prompt_payload,
            priorities=priority_list,
            persona="CISO",
            organization="Acme Corp",
        )
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        workspace_id: str | None = None,
    ) -> None:
        default_headers = {"anthropic-workspace-id": workspace_id} if workspace_id else {}
        self._client = anthropic.Anthropic(api_key=api_key, default_headers=default_headers)
        self._model = model
        self._max_tokens = max_tokens

    # Public API

    def generate(
        self,
        payload: PromptPayload,
        priorities: list[ApplicationPriority],
        persona: str,
        assessment_version: str | None = None,
    ) -> RoadmapOutput:
        """
        Generate a validated RoadmapOutput for the given prompt payload.

        Args:
            payload:            Assembled prompt from assemble_prompt().
            priorities:         Pre-computed ApplicationPriority list (from Jev).
            persona:            One of 'EA', 'CTO', 'CISO'.
            assessment_version: Optional version ID of the assessment input.

        Returns:
            RoadmapOutput combining pre-computed priorities with LLM content.

        Raises:
            LLMCallError:       If the API call fails.
            LLMValidationError: If the response cannot be validated after retry.
        """
        llm_content = self._call_with_retry(payload)
        return self._assemble_output(
            llm_content=llm_content,
            priorities=priorities,
            persona=persona,
            assessment_version=assessment_version,
        )

    # LLM call

    def _call_llm(self, payload: PromptPayload) -> str:
        """
        Send the prompt to the LLM and return the raw response text.
        Override this method to swap LLM providers.
        """
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=payload.system_prompt,
                messages=[{"role": "user", "content": payload.user_message}],
            )
            text_block = next(
                (block for block in message.content if block.type == "text"), None
            )
            if text_block is None:
                raise LLMCallError("LLM response contained no text block.")
            return text_block.text  # type: ignore[union-attr]
        except anthropic.APIError as exc:
            raise LLMCallError(f"LLM API call failed: {exc}") from exc

    def _call_with_retry(self, payload: PromptPayload) -> LLMRoadmapContent:
        """
        Call the LLM and validate the response. Retries once on failure.
        """
        for attempt in range(2):
            raw = self._call_llm(payload)
            try:
                return self._parse_and_validate(raw)
            except LLMValidationError:
                if attempt == 1:
                    raise
        # unreachable, but satisfies type checkers
        raise LLMValidationError("Failed to produce a valid response after retry.")

    # Parsing and validation

    def _parse_and_validate(self, raw: str) -> LLMRoadmapContent:
        """
        Extract JSON from the LLM response and validate it against
        LLMRoadmapContent. Handles responses wrapped in markdown code blocks.
        """
        json_str = self._extract_json(raw)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise LLMValidationError(
                f"LLM response is not valid JSON: {exc}\nRaw response:\n{raw[:500]}"
            ) from exc

        try:
            return LLMRoadmapContent.model_validate(data)
        except ValidationError as exc:
            raise LLMValidationError(
                f"LLM response failed schema validation:\n{exc}"
            ) from exc

    @staticmethod
    def _extract_json(text: str) -> str:
        """
        Extract a JSON object from the response text.
        Handles cases where the LLM wraps its output in a markdown code block.
        Finds the outermost { ... } by locating the first { and last }.
        """
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
        return text.strip()

    # Output assembly

    def _assemble_output(
        self,
        llm_content: LLMRoadmapContent,
        priorities: list[ApplicationPriority],
        persona: str,
        assessment_version: str | None,
    ) -> RoadmapOutput:
        """
        Combine the LLM-generated content with pre-computed priorities
        and provenance metadata into the final RoadmapOutput.
        """
        return RoadmapOutput(
            roadmap_id=f"ROADMAP-{uuid.uuid4().hex[:8].upper()}",
            persona=persona,  # type: ignore[arg-type]
            generated_at=datetime.now(UTC),
            model=self._model,
            prompt_version=PROMPT_VERSION,
            assessment_version=assessment_version,
            priorities=priorities,
            summary=llm_content.summary,
            thirty_day_actions=llm_content.thirty_day_actions,
            sixty_day_actions=llm_content.sixty_day_actions,
            ninety_day_actions=llm_content.ninety_day_actions,
            long_term_roadmap=llm_content.long_term_roadmap,
            assumptions=llm_content.assumptions,
            missing_data=llm_content.missing_data,
        )
