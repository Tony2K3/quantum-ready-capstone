"""
Normalization report and result types.

The report is designed to be written to JSON and read by people: which files
were used, what was merged or skipped, which references could not be
resolved, and which fields are missing for each application.

Messages never include free-text cell contents such as descriptions; at most
they include the single value that caused the problem.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..roadmap.models.enterprise_architecture import EnterpriseArchitecture

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class Origin:
    """Where a raw record came from: file, sheet and spreadsheet row."""

    file: str
    sheet: str | None = None
    row: int | None = None

    def cell(self, column: str) -> str:
        """Location of one cell, e.g. 'apps.xlsx#Sheet1!R3:businessCriticality'."""
        location = self.file
        if self.sheet:
            location += f"#{self.sheet}"
        if self.row is not None:
            location += f"!R{self.row}"
        return f"{location}:{column}"

    def describe(self) -> str:
        parts = [self.file]
        if self.sheet:
            parts.append(f"sheet '{self.sheet}'")
        if self.row is not None:
            parts.append(f"row {self.row}")
        return ", ".join(parts)


class Issue(BaseModel):
    """Something the normalizer noticed while importing."""

    model_config = ConfigDict(extra="forbid")

    severity: Severity
    code: str = Field(description="Stable machine-readable code, e.g. 'placeholder_application'.")
    message: str
    file: str | None = None
    sheet: str | None = None
    row: int | None = None
    column: str | None = None

    @classmethod
    def at(
        cls,
        origin: Origin | None,
        severity: Severity,
        code: str,
        message: str,
        column: str | None = None,
    ) -> Issue:
        return cls(
            severity=severity,
            code=code,
            message=message,
            file=origin.file if origin else None,
            sheet=origin.sheet if origin else None,
            row=origin.row if origin else None,
            column=column,
        )


class FileReport(BaseModel):
    """What happened to one input file."""

    model_config = ConfigDict(extra="forbid")

    path: str
    status: Literal["imported", "skipped", "error"]
    record_types: list[str] = Field(default_factory=list)
    rows: int = 0
    message: str | None = None


class ApplicationMissingData(BaseModel):
    """Tracked fields that have no value for one application."""

    model_config = ConfigDict(extra="forbid")

    application_id: str
    application_name: str
    placeholder: bool = False
    missing_fields: list[str]


class NormalizationReport(BaseModel):
    """Everything a person needs to judge an import."""

    model_config = ConfigDict(extra="forbid")

    source_systems: list[str]
    as_of: date
    application_count: int = 0
    connection_count: int = 0
    files: list[FileReport] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    placeholder_applications: list[str] = Field(
        default_factory=list,
        description="Applications referenced by an interface but not present in the import.",
    )
    incomplete_interfaces: list[str] = Field(
        default_factory=list,
        description="Interfaces missing a provider or consumer; no connection was created.",
    )
    missing_by_application: list[ApplicationMissingData] = Field(default_factory=list)
    field_coverage: dict[str, int] = Field(
        default_factory=dict,
        description="For each tracked field, how many applications have a value.",
    )

    def count(self, severity: Severity) -> int:
        return sum(1 for issue in self.issues if issue.severity == severity)


@dataclass
class NormalizationResult:
    """A validated architecture plus the report describing how it was built."""

    architecture: EnterpriseArchitecture
    report: NormalizationReport


class NormalizationError(Exception):
    """Raised when no valid architecture can be produced. Carries the report."""

    def __init__(self, message: str, report: NormalizationReport) -> None:
        super().__init__(message)
        self.report = report
