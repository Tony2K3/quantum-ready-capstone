"""
Shared provenance types: where a record or a field value came from.

Every Application carries a `field_sources` map so evidence can say whether a
value was imported from an EA tool, supplied by a user, or is missing.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceSystem = Literal["leanix", "bluedolphin", "csv", "placeholder"]

FieldSourceKind = Literal["imported", "inferred", "user_provided", "missing"]

LifecyclePhase = Literal["Plan", "Phase In", "Active", "Phase Out", "End of Life"]

# Lifecycle phases in chronological order.
LIFECYCLE_ORDER: tuple[LifecyclePhase, ...] = (
    "Plan",
    "Phase In",
    "Active",
    "Phase Out",
    "End of Life",
)


class FieldSource(BaseModel):
    """Where one field's value came from."""

    model_config = ConfigDict(extra="forbid")

    kind: FieldSourceKind = Field(
        description="How the value was obtained. 'missing' means no value is available."
    )
    system: str | None = Field(
        default=None,
        description="Source system, e.g. 'leanix' or 'csv'. None when missing.",
    )
    detail: str | None = Field(
        default=None,
        description=(
            "Where exactly the value came from, e.g. "
            "'06_Update_Applications.xlsx#Application updates!R3:businessCriticality', "
            "or how it was derived, e.g. 'derived from hosting_type'. "
            "Never contains the value itself."
        ),
    )


def derive_lifecycle_status(
    dates: dict[LifecyclePhase, date] | None,
    as_of: date,
) -> LifecyclePhase | None:
    """
    Return the lifecycle phase in effect on `as_of`.

    The latest phase whose date is on or before `as_of` wins. If every dated
    phase is in the future, the record is not live yet, so it counts as "Plan".
    """
    if not dates:
        return None
    current: LifecyclePhase | None = None
    for phase in LIFECYCLE_ORDER:
        phase_date = dates.get(phase)
        if phase_date is not None and phase_date <= as_of:
            current = phase
    return current if current is not None else "Plan"
