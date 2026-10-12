"""
Top-level enterprise architecture input model.

This is the single object the roadmap generator receives as input.
It combines the application list and the connection list into one
validated payload.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .application import Application
from .connection import Connection


class EnterpriseArchitecture(BaseModel):
    """
    The complete enterprise architecture input for one roadmap generation run.

    Applications are the nodes and connections are the edges.
    Both are required but connections may be an empty list if the
    connector does not export relationship data.
    """

    applications: list[Application] = Field(
        description="All applications in scope for this assessment."
    )
    connections: list[Connection] = Field(
        default_factory=list,
        description=(
            "Directed relationships between applications. "
            "May be empty if the connector does not export connection data"
        )
    )

    @model_validator(mode="after")
    def connection_ids_must_reference_known_applications(
        self,
    ) -> EnterpriseArchitecture:
        known_ids = {app.id for app in self.applications}
        for conn in self.connections:
            if conn.source_application_id not in known_ids:
                raise ValueError(
                    f"Connection references unknown source application: "
                    f"'{conn.source_application_id}'"
                )
            if conn.target_application_id not in known_ids:
                raise ValueError(
                    f"Connection references unknown target application: "
                    f"'{conn.target_application_id}'"
                )
        return self

    class Config:
        extra = "forbid"
