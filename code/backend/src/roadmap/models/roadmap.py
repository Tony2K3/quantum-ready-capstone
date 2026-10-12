"""
Roadmap schemas for the Decision Cortex roadmap generator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .priority import ApplicationPriority, PriorityLevel

# Type aliases

PersonaType = Literal["EA", "CTO", "CISO"]
Timeframe = Literal["30_days", "60_days", "90_days"]
LongTermYear = Literal["Year 1", "Years 2-3", "Years 4-5"]


# Action and milestone models (LLM-generated)

class RoadmapAction(BaseModel):
    """A single recommended action within the 30/60/90 day plan."""

    id: str = Field(
        description="Unique action identifier (e.g. 'ACTION-001'). Stable across roadmap versions."
    )
    application_id: str | None = Field(
        default=None,
        description=(
            "ID of the application this action relates to. "
            "None for organisation-wide actions."
        )
    )
    application_name: str | None = Field(
        default=None,
        description="Human-readable application name. None for organisation-wide actions."
    )
    action: str = Field(
        description="Short imperative description of the action (e.g. 'Confirm cryptographic dependencies')."
    )
    detail: str | None = Field(
        default=None,
        description="Longer explanation of what this action involves and why it is needed."
    )
    reason: str = Field(
        description="Why this action is recommended at this point in time."
    )
    priority: PriorityLevel = Field(
        description="Priority of this action within its timeframe."
    )
    timeframe: Timeframe = Field(
        description="Which phase of the 30/60/90 day plan this action belongs to."
    )
    evidence: list[str] = Field(
        description=(
            "References to assessment data that support this action. "
            "Should be drawn from the application's key_factors in ApplicationPriority. "
            "Format: '{application_id}.{field} = {value}'."
        )
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of other actions that must be completed before this one."
    )
    owner: str | None = Field(
        default=None,
        description="Suggested owner, taken from the application's owner field where available."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made when generating this action."
    )


class LongTermMilestone(BaseModel):
    """A high-level milestone in the 2-5 year strategic roadmap."""

    year: LongTermYear = Field(
        description="Which year range this milestone belongs to."
    )
    title: str = Field(
        description="Short title for this milestone."
    )
    description: str = Field(
        description="Plain-language description of the goal and what achieving it means."
    )
    application_ids: list[str] = Field(
        default_factory=list,
        description="Applications in scope for this milestone."
    )
    goals: list[str] = Field(
        description="Specific outcomes that define completion of this milestone."
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Milestone titles or action IDs that must be completed before this one."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions underlying this milestone."
    )


# LLM output schema

class LLMRoadmapContent(BaseModel):
    """
    The schema the LLM is asked to produce.

    The LLM's job is to generate actions and explanations grounded in
    pre-computed priorities.
    """

    summary: str = Field(
        description=(
            "Executive summary of the roadmap in 2-4 sentences. "
            "Tone and emphasis should reflect the selected persona."
        )
    )
    thirty_day_actions: list[RoadmapAction] = Field(
        description="Recommended actions for the first 30 days (understand and prepare)."
    )
    sixty_day_actions: list[RoadmapAction] = Field(
        description="Recommended actions for days 31-60 (plan and assess)."
    )
    ninety_day_actions: list[RoadmapAction] = Field(
        description="Recommended actions for days 61-90 (begin execution)."
    )
    long_term_roadmap: list[LongTermMilestone] = Field(
        description="High-level milestones for the 2-5 year strategic horizon."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Global assumptions made when generating this roadmap."
    )
    missing_data: list[str] = Field(
        default_factory=list,
        description=(
            "Assessment fields or applications where data was absent. "
            "Format: '{application_id}.{field}' or a plain description."
        )
    )

    class Config:
        extra = "forbid"


# Final combined output

class RoadmapOutput(BaseModel):
    """
    The complete output of one roadmap generation run.

    Combines:
      - Metadata
      - Pre-computed priorities (from the deterministic scoring step)
      - LLM-generated content (summary, actions, milestones)
    """

    # Metadata

    roadmap_id: str = Field(
        description="Unique identifier for this roadmap run."
    )
    persona: PersonaType = Field(
        description="The persona this roadmap was generated for."
    )
    generated_at: datetime = Field(
        description="Timestamp of generation."
    )
    model: str = Field(
        description="LLM provider and model used (e.g. 'anthropic/claude-3-5-sonnet')."
    )
    prompt_version: str = Field(
        description="Version of the system prompt used (e.g. 'v1.0.0')."
    )
    assessment_version: str | None = Field(
        default=None,
        description="Version or ID of the assessment input this roadmap was generated from."
    )

    # Precomputed (deterministic) fields

    priorities: list[ApplicationPriority] = Field(
        description=(
            "Priority ranking of all assessed applications, highest urgency first. "
            "Produced by the deterministic priority scoring step."
        )
    )

    # LLM-generated fields

    summary: str = Field(description="Executive summary from the LLM.")
    thirty_day_actions: list[RoadmapAction] = Field(
        description="Recommended actions for the first 30 days."
    )
    sixty_day_actions: list[RoadmapAction] = Field(
        description="Recommended actions for days 31-60."
    )
    ninety_day_actions: list[RoadmapAction] = Field(
        description="Recommended actions for days 61-90."
    )
    long_term_roadmap: list[LongTermMilestone] = Field(
        description="High-level milestones for the 2-5 year strategic horizon."
    )
    assumptions: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)

    class Config:
        extra = "forbid"
