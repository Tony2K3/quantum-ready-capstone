"""
LLM context assembler.

Takes the outputs of the deterministic pipeline steps and assembles them
into a structured prompt ready to send to the LLM.

Output is a PromptPayload containing:
  - system_prompt: the versioned system prompt with persona instructions
  - user_message:  the context block + generation instructions
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..models.enterprise_architecture import EnterpriseArchitecture
from ..models.priority import ApplicationPriority
from ..models.roadmap import LLMRoadmapContent
from .prompts import PROMPT_VERSION, build_system_prompt

# Type alias
PersonaType = str  # "EA" | "CTO" | "CISO"


# Output

@dataclass(frozen=True)
class PromptPayload:
    """
    The assembled prompt, ready to send to the LLM.

    system_prompt: passed as the system message.
    user_message:  passed as the user message.
    prompt_version: recorded in RoadmapOutput for provenance.
    """
    system_prompt: str
    user_message: str
    prompt_version: str


# Context block builders

def _priority_level_counts(priorities: list[ApplicationPriority]) -> str:
    counts: dict[str, int] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for p in priorities:
        counts[p.priority_level] = counts.get(p.priority_level, 0) + 1
    parts = [f"{level}: {n}" for level, n in counts.items() if n > 0]
    return "  |  ".join(parts)


def _format_application_block(
    priority: ApplicationPriority,
    rank: int,
) -> str:
    lines = [
        f"[{rank}] {priority.application_name} ({priority.application_id})",
        f" — {priority.priority_level.upper()}",
        f"    Priority score: {priority.priority_score:.1f}",
    ]

    if priority.key_factors:
        factors = ", ".join(priority.key_factors)
        lines.append(f"    Key factors: {factors}")

    if priority.critical_check_failures:
        failures = ", ".join(priority.critical_check_failures)
        lines.append(f"    Critical check failures: {failures}")

    if priority.missing_fields:
        missing = ", ".join(priority.missing_fields)
        lines.append(f"    Missing data: {missing}")

    return "\n".join(lines)


def _build_context_block(
    priorities: list[ApplicationPriority],
    architecture: EnterpriseArchitecture,
    organization: str,
) -> str:
    lines: list[str] = []

    # Header
    lines += [
        "ASSESSMENT CONTEXT",
        "==================",
        f"Organisation: {organization}",
        f"Applications assessed: {len(priorities)}",
        _priority_level_counts(priorities),
        "",
    ]

    # Applications in priority order
    lines += [
        "APPLICATIONS (highest priority first)",
        "--------------------------------------",
    ]
    for rank, priority in enumerate(priorities, start=1):
        lines.append(_format_application_block(priority, rank))
        lines.append("")

    # Key dependencies
    if architecture.connections:
        lines += ["KEY DEPENDENCIES", "----------------"]
        for conn in architecture.connections:
            dep_type = f", {conn.dependency_type}" if conn.dependency_type else ""
            lines.append(
                f"- {conn.source_application_id} → {conn.target_application_id}"
                f" ({conn.relationship}{dep_type})"
            )
        lines.append("")

    # Aggregate missing data
    all_missing = [
        f"{p.application_id}.{field}"
        for p in priorities
        for field in p.missing_fields
    ]
    if all_missing:
        lines += ["MISSING DATA", "------------"]
        for item in all_missing:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def _build_generation_instructions(persona: PersonaType) -> str:
    return f"""\
TASK
----
Using the assessment context above, generate a quantum-readiness roadmap
for the {persona} persona.

Instructions:
- Follow the priority order shown above when assigning actions to timeframes.
  Critical and High priority applications should drive the 30-day actions.
- Generate at most 3 actions per timeframe. Focus on the highest impact.
- Every action must include at least one evidence reference drawn from the
  key_factors listed for that application.
- For every missing data field listed above, include a 30-day action to
  gather that information. Do not assume a value for missing fields.
- Sequence dependent applications correctly: if APP-A depends on APP-B,
  APP-B's migration actions should come before APP-A's.
- The summary should be 2-4 sentences and reflect the {persona} persona's
  primary concerns.
- Long-term roadmap should have at most 3 milestones.

Respond with a single valid JSON object matching the output schema in the
system prompt. No text before or after the JSON.
"""


# Public API

def assemble_prompt(
    priorities: list[ApplicationPriority],
    architecture: EnterpriseArchitecture,
    persona: PersonaType,
    organization: str = "the organisation",
) -> PromptPayload:
    """
    Assemble the full prompt payload for a roadmap generation call.

    Args:
        priorities:    Ranked list of ApplicationPriority objects from the
                       priority scoring step (Jev).
        architecture:  The validated enterprise architecture input, used for
                       dependency context.
        persona:       One of 'EA', 'CTO', 'CISO'.
        organization:  Human-readable organisation name for the context block.

    Returns:
        PromptPayload with system_prompt, user_message, and prompt_version.
    """
    # Sort priorities highest -> lowest before assembling (defensive — should
    # already be sorted by the scoring step, but we enforce it here)
    sorted_priorities = sorted(
        priorities,
        key=lambda p: p.priority_score,
        reverse=True,
    )

    output_schema = json.dumps(
        LLMRoadmapContent.model_json_schema(), indent=2
    )

    system_prompt = build_system_prompt(persona, output_schema)
    context_block = _build_context_block(sorted_priorities, architecture, organization)
    generation_instructions = _build_generation_instructions(persona)

    user_message = f"{context_block}\n{generation_instructions}"

    return PromptPayload(
        system_prompt=system_prompt,
        user_message=user_message,
        prompt_version=PROMPT_VERSION,
    )
