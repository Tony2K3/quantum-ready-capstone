"""
Native CSV adapter: our own two-file template -> raw records.

  applications.csv  one row per application; columns are Application field names
  connections.csv   one row per connection; columns are Connection field names

List columns use ';' as the separator. Lifecycle dates use the columns in
CSV_LIFECYCLE_COLUMNS (ISO dates). This is also the interim way for users
to supply the crypto and risk fields that EA tools do not carry: export,
fill in the columns, and import the CSV on top of the LeanIX data.

File roles are detected from the header, not the file name.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..roadmap.models.provenance import SourceSystem
from .mappings import CSV_LIFECYCLE_COLUMNS
from .records import RawApplication, RawBundle, RawConnection, Ref
from .report import FileReport, Issue, Origin
from .tabular import (
    Sheet,
    as_text,
    expand_paths,
    parse_date,
    read_table_file,
    split_list,
)

SOURCE: SourceSystem = "csv"

APPLICATION_COLUMNS: tuple[str, ...] = (
    "id",
    "name",
    "description",
    "business_unit",
    "owner",
    "business_criticality",
    "data_sensitivity",
    "data_longevity",
    "vendor_dependency",
    "technology_stack",
    "deployment_environment",
    "hosting_type",
    "network_exposure",
    "network_protocols",
    "cryptographic_dependencies",
    "crypto_agility",
    "key_management_type",
    "pqc_readiness",
    "lifecycle_status",
    *CSV_LIFECYCLE_COLUMNS,
    "time_classification",
    "technical_fit",
    "it_components",
    "data_objects",
)

CONNECTION_COLUMNS: tuple[str, ...] = (
    "source_application_id",
    "target_application_id",
    "relationship",
    "dependency_type",
    "criticality",
    "interface_id",
    "name",
    "description",
    "via",
    "data_objects",
    "frequency",
    "direction",
    "lifecycle_status",
    *CSV_LIFECYCLE_COLUMNS,
)

_APP_LIST_FIELDS = {"network_protocols", "cryptographic_dependencies", "it_components", "data_objects"}
_CONNECTION_LIST_FIELDS = {"via", "data_objects"}


def load_native_csv(paths: Iterable[str | Path]) -> RawBundle:
    """Read native applications/connections CSV files from files and/or folders."""
    bundle = RawBundle(source_system=SOURCE)
    for path in expand_paths(paths, (".csv",)):
        try:
            sheet = read_table_file(path)[0]
        except Exception as exc:  # noqa: BLE001 - reported, not fatal
            bundle.files.append(FileReport(
                path=str(path), status="error", message=f"Could not read file ({type(exc).__name__})."
            ))
            bundle.issues.append(Issue(
                severity="error", code="unreadable_file", file=path.name,
                message=f"Could not read {path.name} ({type(exc).__name__}); it was skipped.",
            ))
            continue

        header = set(sheet.header)
        if "source_application_id" in header:
            rows = _load_connections(sheet, path, bundle)
            record_type = "Connection"
        elif {"id", "name"} <= header:
            rows = _load_applications(sheet, path, bundle)
            record_type = "Application"
        else:
            bundle.files.append(FileReport(
                path=str(path), status="skipped",
                message="Not a native applications or connections CSV (see the template).",
            ))
            continue
        bundle.files.append(FileReport(
            path=str(path), status="imported", record_types=[record_type], rows=rows
        ))
    return bundle


def write_templates(directory: str | Path) -> list[Path]:
    """Write blank applications.csv and connections.csv (header rows only)."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for file_name, columns in (
        ("applications.csv", APPLICATION_COLUMNS),
        ("connections.csv", CONNECTION_COLUMNS),
    ):
        path = target / file_name
        path.write_text(",".join(columns) + "\n", encoding="utf-8")
        written.append(path)
    return written


def _report_unknown_columns(
    sheet: Sheet, known: tuple[str, ...], path: Path, bundle: RawBundle, action: str
) -> set[str]:
    unknown = {c for c in sheet.header if c and c not in known}
    if unknown:
        bundle.issues.append(Issue(
            severity="warning", code="unknown_column", file=path.name,
            message=f"{path.name}: unknown column(s) {', '.join(sorted(unknown))}; {action}.",
        ))
    return unknown


def _lifecycle_dates(
    row: dict[str, Any], origin: Origin, bundle: RawBundle
) -> dict[str, Any]:
    dates: dict[str, Any] = {}
    for column, phase in CSV_LIFECYCLE_COLUMNS.items():
        if as_text(row.get(column)) is None:
            continue
        try:
            dates[phase] = parse_date(row[column])
        except ValueError:
            bundle.issues.append(Issue.at(
                origin, "error", "invalid_date",
                f"Could not read {column} value {as_text(row[column])!r} as a date "
                "(expected YYYY-MM-DD); it was ignored.",
                column=column,
            ))
    return dates


def _load_applications(sheet: Sheet, path: Path, bundle: RawBundle) -> int:
    unknown = _report_unknown_columns(
        sheet, APPLICATION_COLUMNS, path, bundle, "kept in extra_attributes"
    )
    count = 0
    for row_number, row in sheet.rows:
        origin = Origin(file=path.name, row=row_number)
        app_id = as_text(row.get("id"))
        name = as_text(row.get("name"))
        if app_id is None or name is None:
            bundle.issues.append(Issue.at(
                origin, "error", "missing_required",
                "Row has no id or no name; it was skipped.",
                column="id" if app_id is None else "name",
            ))
            continue

        app = RawApplication(name=name, origin=origin, source_system=SOURCE, explicit_id=app_id)
        for column in APPLICATION_COLUMNS:
            if column in ("id", "name") or column in CSV_LIFECYCLE_COLUMNS:
                continue
            value = row.get(column)
            if as_text(value) is None:
                continue
            parsed = split_list(value) if column in _APP_LIST_FIELDS else as_text(value)
            app.set(column, parsed, column)
        dates = _lifecycle_dates(row, origin, bundle)
        if dates:
            app.set("lifecycle_dates", dates, "lifecycle_*")
        for column in unknown:
            text = as_text(row.get(column))
            if text is not None:
                app.extra[column] = text
        bundle.applications.append(app)
        count += 1
    return count


def _load_connections(sheet: Sheet, path: Path, bundle: RawBundle) -> int:
    _report_unknown_columns(sheet, CONNECTION_COLUMNS, path, bundle, "they were ignored")
    count = 0
    for row_number, row in sheet.rows:
        origin = Origin(file=path.name, row=row_number)
        source = as_text(row.get("source_application_id"))
        target = as_text(row.get("target_application_id"))
        if source is None or target is None:
            bundle.issues.append(Issue.at(
                origin, "error", "missing_required",
                "Row has no source_application_id or target_application_id; it was skipped.",
            ))
            continue

        conn = RawConnection(
            origin=origin,
            source_system=SOURCE,
            name=as_text(row.get("name")),
            interface_code=as_text(row.get("interface_id")),
            consumers=[Ref(source, "id_or_name")],
            providers=[Ref(target, "id_or_name")],
        )
        for column in CONNECTION_COLUMNS:
            if column in (
                "source_application_id", "target_application_id", "interface_id", "name"
            ) or column in CSV_LIFECYCLE_COLUMNS:
                continue
            value = row.get(column)
            if as_text(value) is None:
                continue
            conn.values[column] = (
                split_list(value) if column in _CONNECTION_LIST_FIELDS else as_text(value)
            )
        dates = _lifecycle_dates(row, origin, bundle)
        if dates:
            conn.values["lifecycle_dates"] = dates
        bundle.connections.append(conn)
        count += 1
    return count
