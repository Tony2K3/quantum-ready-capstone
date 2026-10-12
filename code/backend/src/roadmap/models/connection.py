"""
Connection input schema for the Decision Cortex roadmap generator.

Applications are nodes. Connections are the edges between them.
Forms an EA graph used for reasoning about migration sequencing and downstream impact.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Type aliases

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

    @model_validator(mode="after")
    def source_and_target_must_differ(self) -> Connection:
        if self.source_application_id == self.target_application_id:
            raise ValueError(
                "source_application_id and target_application_id must be different"
            )
        return self

    class Config:
        extra = "forbid"
