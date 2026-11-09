"""
LeanIX adapter: Excel (or CSV) inventory exports and import sheets -> raw records.

LeanIX sheet layout:
  - Row 1 holds field keys (e.g. 'relInterfaceToProviderApplication').
  - Row 2 usually repeats them as display labels ('Provider Application');
    it is detected and skipped.
  - A 'ReadMe' sheet documents the columns; it is ignored.
  - Each row has a 'type' (Application, Interface, ITComponent, ...).
  - List values are separated by ';'. Relations reference fact sheets by
    display name.

Files are applied in order: unnumbered files (base exports) first, then
numbered update files ('06_Update_...', '07_...') in ascending order, so
later updates override earlier values.

Mapping decisions:
  - Interface provider/consumer becomes a connection from consumer (source)
    to provider (target): the consumer depends on the provider.
  - Middleware on an interface (IT components) goes to `Connection.via`.
  - Business criticality maps 4 levels -> 3; the original value is kept.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..roadmap.models.provenance import SourceSystem
from .mappings import (
    LEANIX_BUSINESS_CRITICALITY,
    LEANIX_DATA_FLOW_DIRECTION,
    LEANIX_FREQUENCY,
    LEANIX_HOSTING_TYPE,
    LEANIX_INTERFACE_TYPE,
    LEANIX_LIFECYCLE,
    LEANIX_TECHNICAL_FIT,
    LEANIX_TIME_CLASSIFICATION,
)
from .records import RawApplication, RawBundle, RawComponentLink, RawConnection, Ref
from .report import FileReport, Issue, Origin
from .tabular import (
    as_text,
    expand_paths,
    norm_key,
    parse_date,
    read_table_file,
    split_list,
)

SOURCE: SourceSystem = "leanix"
SUPPORTED_TYPES = ("Application", "Interface", "ITComponent")

_INTERFACE_CODE = re.compile(r"\bINT-\d+\b", re.IGNORECASE)
_NUMBER_PREFIX = re.compile(r"^(\d+)[_\- ]")

# Columns handled explicitly; anything else non-empty goes to extra_attributes.
_COMMON_COLUMNS = {"id", "type", "name", "displayName", "description", "externalId"}
_LIST_COLUMN_PREFIXES = ("rel", "tags:", "subscriptions:")


def file_order(path: Path) -> tuple[int, int, str]:
    """Unnumbered files first, then numbered update files in ascending order."""
    match = _NUMBER_PREFIX.match(path.name)
    if match:
        return (1, int(match.group(1)), path.name.lower())
    return (0, 0, path.name.lower())


def is_template(path: Path) -> bool:
    return "template" in path.stem.lower()


def load_leanix(
    paths: Iterable[str | Path],
    include_templates: bool = False,
) -> RawBundle:
    """
    Read LeanIX exports from files and/or folders.

    Files whose name contains 'Template' are skipped unless
    `include_templates` is set: LeanIX templates contain example rows
    ('Example Application') that would pollute a real import.
    """
    bundle = RawBundle(source_system=SOURCE)
    for path in sorted(expand_paths(paths), key=file_order):
        if is_template(path) and not include_templates:
            bundle.files.append(FileReport(
                path=str(path), status="skipped",
                message="Looks like a LeanIX template; skipped (use include_templates to import it).",
            ))
            continue
        _load_file(path, bundle)
    return bundle


def _load_file(path: Path, bundle: RawBundle) -> None:
    file_label = path.name
    try:
        sheets = read_table_file(path)
    except Exception as exc:  # noqa: BLE001 - any unreadable file is reported, not fatal
        bundle.files.append(FileReport(
            path=str(path), status="error", message=f"Could not read file ({type(exc).__name__})."
        ))
        bundle.issues.append(Issue(
            severity="error", code="unreadable_file", file=file_label,
            message=f"Could not read {file_label} ({type(exc).__name__}); it was skipped.",
        ))
        return

    seen_types: list[str] = []
    imported_rows = 0
    for sheet in sheets:
        if sheet.name and sheet.name.strip().lower() == "readme":
            continue
        if "type" not in sheet.header or "name" not in sheet.header:
            continue
        for row_number, row in sheet.rows:
            record_type = as_text(row.get("type"))
            if record_type is None or _is_label_row(row):
                continue
            if record_type not in seen_types:
                seen_types.append(record_type)
            origin = Origin(file=file_label, sheet=sheet.name, row=row_number)
            if record_type == "Application":
                _application_row(row, origin, bundle)
            elif record_type == "Interface":
                _interface_row(row, origin, bundle)
            elif record_type == "ITComponent":
                _component_row(row, origin, bundle)
            else:
                continue
            imported_rows += 1

    if imported_rows:
        bundle.files.append(FileReport(
            path=str(path), status="imported", record_types=seen_types, rows=imported_rows
        ))
    else:
        message = (
            f"No {', '.join(SUPPORTED_TYPES)} rows"
            + (f" (found: {', '.join(seen_types)})" if seen_types else "")
            + "."
        )
        bundle.files.append(FileReport(
            path=str(path), status="skipped", record_types=seen_types, message=message
        ))
        bundle.issues.append(Issue(
            severity="info", code="skipped_file", file=file_label,
            message=f"{file_label}: {message} Nothing was imported from it.",
        ))


def _is_label_row(row: dict[str, Any]) -> bool:
    """LeanIX repeats column labels in row 2 ('ID', 'Type', 'Name')."""
    return as_text(row.get("type")) == "Type" or as_text(row.get("id")) == "ID"


# Shared column helpers

def _map_enum(
    row: dict[str, Any],
    column: str,
    table: dict[str, str],
    origin: Origin,
    issues: list[Issue],
) -> str | None:
    """Map a coded value; unknown values are reported and returned as None."""
    raw = as_text(row.get(column))
    if raw is None:
        return None
    if raw in table:
        return table[raw]
    issues.append(Issue.at(
        origin, "warning", "unrecognized_value",
        f"Unrecognized {column} value {raw!r}; kept in extra_attributes.",
        column=column,
    ))
    return None


def _lifecycle_dates(row: dict[str, Any], origin: Origin, issues: list[Issue]) -> dict[str, Any]:
    dates: dict[str, Any] = {}
    for column, value in row.items():
        if not column.startswith("lifecycle:") or as_text(value) is None:
            continue
        phase = LEANIX_LIFECYCLE.get(column.split(":", 1)[1])
        if phase is None:
            continue
        try:
            dates[phase] = parse_date(value)
        except ValueError:
            issues.append(Issue.at(
                origin, "warning", "invalid_date",
                f"Could not read {column} value {as_text(value)!r} as a date; it was ignored.",
                column=column,
            ))
    return dates


def _extra_value(column: str, value: Any) -> str | list[str] | None:
    if column.startswith(_LIST_COLUMN_PREFIXES):
        items = split_list(value)
        return items or None
    return as_text(value)


# Row handlers

_APP_HANDLED = _COMMON_COLUMNS | {
    "businessCriticality",
    "lxHostingType",
    "lxTimeClassification",
    "technicalSuitability",
    "subscriptions:RESPONSIBLE",
    "relApplicationToOrganization",
}


def _application_row(row: dict[str, Any], origin: Origin, bundle: RawBundle) -> None:
    name = as_text(row.get("name"))
    if name is None:
        bundle.issues.append(Issue.at(
            origin, "warning", "missing_name", "Application row has no name; it was skipped.",
            column="name",
        ))
        return

    app = RawApplication(
        name=name,
        origin=origin,
        source_system=SOURCE,
        source_id=as_text(row.get("id")),
        external_ids=set(split_list(row.get("externalId"))),
    )
    display_name = as_text(row.get("displayName"))
    if display_name:
        app.aliases.add(norm_key(display_name))

    description = as_text(row.get("description"))
    if description:
        app.set("description", description, "description")

    enum_columns = (
        ("businessCriticality", "business_criticality", LEANIX_BUSINESS_CRITICALITY),
        ("lxHostingType", "hosting_type", LEANIX_HOSTING_TYPE),
        ("lxTimeClassification", "time_classification", LEANIX_TIME_CLASSIFICATION),
        ("technicalSuitability", "technical_fit", LEANIX_TECHNICAL_FIT),
    )
    for column, field_name, table in enum_columns:
        raw = as_text(row.get(column))
        mapped = _map_enum(row, column, table, origin, bundle.issues)
        if mapped is not None:
            app.set(field_name, mapped, column)
        if raw is not None and (mapped is None or column == "businessCriticality"):
            # Keep the original: always for criticality (4 -> 3 levels loses
            # detail), and for any value we could not map.
            app.extra[column] = raw

    owners = split_list(row.get("subscriptions:RESPONSIBLE"))
    if owners:
        app.set("owner", "; ".join(owners), "subscriptions:RESPONSIBLE")

    organizations = split_list(row.get("relApplicationToOrganization"))
    if organizations:
        app.set("business_unit", "; ".join(organizations), "relApplicationToOrganization")

    dates = _lifecycle_dates(row, origin, bundle.issues)
    if dates:
        app.set("lifecycle_dates", dates, "lifecycle")

    for column, value in row.items():
        if column in _APP_HANDLED or column.startswith("lifecycle:"):
            continue
        extra = _extra_value(column, value)
        if extra is not None:
            app.extra[column] = extra

    bundle.applications.append(app)


def _interface_row(row: dict[str, Any], origin: Origin, bundle: RawBundle) -> None:
    name = as_text(row.get("name")) or as_text(row.get("displayName"))
    if name is None:
        bundle.issues.append(Issue.at(
            origin, "warning", "missing_name", "Interface row has no name; it was skipped.",
            column="name",
        ))
        return

    code_match = _INTERFACE_CODE.search(name)
    conn = RawConnection(
        origin=origin,
        source_system=SOURCE,
        name=name,
        source_id=as_text(row.get("id")),
        interface_code=code_match.group(0).upper() if code_match else None,
        external_ids=set(split_list(row.get("externalId"))),
        consumers=[Ref(n) for n in split_list(row.get("relInterfaceToConsumerApplication"))],
        providers=[Ref(n) for n in split_list(row.get("relInterfaceToProviderApplication"))],
    )

    relationship = _map_enum(row, "interfaceType", LEANIX_INTERFACE_TYPE, origin, bundle.issues)
    if relationship:
        conn.values["relationship"] = relationship
    frequency = _map_enum(row, "frequency", LEANIX_FREQUENCY, origin, bundle.issues)
    if frequency:
        conn.values["frequency"] = frequency
    direction = _map_enum(row, "dataFlowDirection", LEANIX_DATA_FLOW_DIRECTION, origin, bundle.issues)
    if direction is None:
        if "↔" in name:
            direction = "bidirectional"
        elif "→" in name:
            direction = "unidirectional"
    if direction:
        conn.values["direction"] = direction

    via = split_list(row.get("relInterfaceToITComponent"))
    if via:
        conn.values["via"] = via
    data_objects = split_list(row.get("relInterfaceToDataObject"))
    if data_objects:
        conn.values["data_objects"] = data_objects
    description = as_text(row.get("description"))
    if description:
        conn.values["description"] = description
    dates = _lifecycle_dates(row, origin, bundle.issues)
    if dates:
        conn.values["lifecycle_dates"] = dates

    bundle.connections.append(conn)


def _component_row(row: dict[str, Any], origin: Origin, bundle: RawBundle) -> None:
    name = as_text(row.get("displayName")) or as_text(row.get("name"))
    if name is None:
        return
    for application in split_list(row.get("relITComponentToApplication")):
        bundle.component_links.append(
            RawComponentLink(component=name, application=Ref(application), origin=origin)
        )
