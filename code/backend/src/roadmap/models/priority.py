"""
Priority output schema — produced by the deterministic priority scoring step,
not by the LLM.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PriorityLevel = Literal["Critical", "High", "Medium", "Low"]


class ApplicationPriority(BaseModel):
    """
    The deterministic priority assessment for a single application.
    Produced by the priority scoring engine before the LLM is called.
    """

    application_id: str = Field(
        description="ID of the application."
    )
    application_name: str = Field(
        description="Human-readable application name."
    )
    priority_level: PriorityLevel = Field(
        description="Priority level derived from scoring factors."
    )
    priority_score: float = Field(
        description=(
            "Numeric priority score (0-100, higher = more urgent). "
            "Produced by the priority scoring engine."
        )
    )
    key_factors: list[str] = Field(
        description=(
            "The specific field values and findings that drove this priority. "
            "Format: '{application_id}.{field} = {value}'. "
            "Passed to the LLM as evidence to cite in action recommendations."
        )
    )
    critical_check_failures: list[str] = Field(
        default_factory=list,
        description="Jev dimension IDs that scored above 75% of their maximum scale."
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Application fields that were None at assessment time. "
            "Surfaced here so the LLM can recommend data-gathering actions."
        )
    )
