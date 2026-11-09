"""
Raw records produced by source adapters.

Adapters translate each source format into these records using the model's
field names, but they do not build Pydantic objects. The shared `assemble()`
step merges duplicates, resolves references, validates and reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..roadmap.models.provenance import SourceSystem
from .report import FileReport, Issue, Origin

RefKind = Literal["name", "id", "id_or_name"]


@dataclass(frozen=True)
class Ref:
    """
    A reference to an application.

    LeanIX references applications by display name ('name'). The native CSV
    uses our application ids, falling back to names ('id_or_name').
    Only 'name' references create placeholder applications when unresolved.
    """

    text: str
    kind: RefKind = "name"


@dataclass
class FieldValue:
    """A field value plus where it came from."""

    value: Any
    system: str
    origin: Origin | None = None
    column: str | None = None
    note: str | None = None

    @property
    def detail(self) -> str | None:
        """Cell location, or a note for derived values. Never the value itself."""
        if self.note:
            return self.note
        if self.origin and self.column:
            return self.origin.cell(self.column)
        return None


@dataclass
class RawApplication:
    name: str
    origin: Origin
    source_system: SourceSystem
    source_id: str | None = None
    explicit_id: str | None = None
    aliases: set[str] = field(default_factory=set)
    external_ids: set[str] = field(default_factory=set)
    values: dict[str, FieldValue] = field(default_factory=dict)
    extra: dict[str, str | list[str]] = field(default_factory=dict)

    def set(self, field_name: str, value: Any, column: str) -> None:
        """Record a value read from `column` of this record's row."""
        self.values[field_name] = FieldValue(value, self.source_system, self.origin, column)


@dataclass
class RawConnection:
    origin: Origin
    source_system: SourceSystem
    name: str | None = None
    source_id: str | None = None
    interface_code: str | None = None
    external_ids: set[str] = field(default_factory=set)
    # Consumers depend on providers: source = consumer, target = provider.
    consumers: list[Ref] = field(default_factory=list)
    providers: list[Ref] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawComponentLink:
    """An IT component attached to an application by an ITComponent record."""

    component: str
    application: Ref
    origin: Origin


@dataclass
class RawBundle:
    """Everything one adapter produced."""

    source_system: SourceSystem
    applications: list[RawApplication] = field(default_factory=list)
    connections: list[RawConnection] = field(default_factory=list)
    component_links: list[RawComponentLink] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    files: list[FileReport] = field(default_factory=list)
