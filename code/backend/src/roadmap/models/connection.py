"""
Connection input schema for the Decision Cortex roadmap generator.

Applications are nodes. Connections are the edges between them.
Forms an EA graph used for reasoning about migration sequencing and downstream impact.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .provenance import LifecyclePhase, SourceSystem

# Type aliases

Frequency = Literal[
    "Real-time", "Hourly", "Daily", "Weekly", "Monthly", "Yearly", "On Demand"
]
Direction = Literal["unidirectional", "bidirectional"]

RelationshipType = Literal[
    "API",
    "Database",
    "Message Queue",
    "File Transfer",
    "Authentication",
    "Service Dependency",
    "Other",
]

DependencyType = Literal[
    "Required",   # source cannot function without target
    "Optional",   # source degrades or loses a feature, but still operates
]


class Connection(BaseModel):
    """
    A directed relationship between two applications.

    The source application uses the target application.

    Example:
        Customer Portal -> Payment Service (API, Required)
        Payment Service -> Payment Database (Database, Required)
    """

    source_application_id: str = Field(
        description=(
            "ID of the application that initiates or depends on the connection. "
            "Must match an 'id' in the accompanying applications list."
        )
    )
    target_application_id: str = Field(
        description=(
            "ID of the application being called or depended upon. "
            "Must match an 'id' in the accompanying applications list."
        )
    )
    relationship: RelationshipType = Field(
        description=(
            "The nature of the interaction between the two applications."
        )
    )
    dependency_type: DependencyType | None = Field(
        default=None,
        description=(
            "Whether the source application requires the target to function. "
            "None = not assessed or not provided by the connector. "
            "The roadmap generator should treat None conservatively."
        )
    )
    criticality: Literal["Low", "Medium", "High"] | None = Field(
        default=None,
        description=(
            "How critical this specific connection is. A High-criticality "
            "connection between two applications may influence migration "
            "sequencing even if one application is otherwise low priority."
        )
    )
    description: str | None = Field(
        default=None,
        description="Free-text description of the connection (from the connector)."
    )

    # Interface detail (from EA tools)

    interface_id: str | None = Field(
        default=None,
        description=(
            "Identifier of the interface this connection came from (e.g. 'INT-010'). "
            "Several connections may share the same pair of applications but "
            "never the same interface_id and pair."
        )
    )
    name: str | None = Field(
        default=None,
        description="Interface name as recorded in the EA tool."
    )
    via: list[str] | None = Field(
        default=None,
        description=(
            "Middleware or infrastructure the data passes through (e.g. 'Boomi SaaS "
            "Hosting'). Kept here instead of as graph nodes; TLS often terminates there."
        )
    )
    data_objects: list[str] | None = Field(
        default=None,
        description="Business data objects carried by this connection."
    )
    frequency: Frequency | None = Field(
        default=None,
        description="How often data flows over the connection."
    )
    direction: Direction | None = Field(
        default=None,
        description=(
            "'bidirectional' when data flows both ways. The source/target "
            "dependency direction is unaffected."
        )
    )
    lifecycle_status: LifecyclePhase | None = Field(
        default=None,
        description="Lifecycle phase of the interface at import time."
    )
    lifecycle_dates: dict[LifecyclePhase, date] | None = Field(
        default=None,
        description="Start date of each known lifecycle phase."
    )

    # Provenance

    source_system: SourceSystem | None = Field(
        default=None,
        description="System this connection was imported from."
    )
    source_id: str | None = Field(
        default=None,
        description="The interface's identifier in the source system."
    )

    @model_validator(mode="after")
    def source_and_target_must_differ(self) -> Connection:
        if self.source_application_id == self.target_application_id:
            raise ValueError(
                "source_application_id and target_application_id must be different"
            )
        return self

    model_config = ConfigDict(extra="forbid")
