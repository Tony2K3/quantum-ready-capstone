"""
Shared assembly step: raw records from any adapter -> validated EnterpriseArchitecture.

Steps:
  1. Merge duplicate application and interface records (later records win
     for non-empty values).
  2. Assign stable application ids.
  3. Resolve interface references; create placeholder applications for
     names that are not in the import.
  4. Attach IT components and derive a few values that are direct
     consequences of imported data (deployment environment from hosting
     type, lifecycle status from dates, data objects from interfaces).
     Nothing is guessed: risk and cryptography fields stay missing.
  5. Validate with the Pydantic models, dropping only the offending values.
  6. Build the report.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from ..roadmap.models.application import TRACKED_FIELDS, Application
from ..roadmap.models.connection import Connection
from ..roadmap.models.enterprise_architecture import EnterpriseArchitecture
from ..roadmap.models.provenance import (
    FieldSource,
    SourceSystem,
    derive_lifecycle_status,
)
from .mappings import HOSTING_TO_DEPLOYMENT
from .records import FieldValue, RawApplication, RawBundle, RawConnection, Ref
from .report import (
    ApplicationMissingData,
    Issue,
    NormalizationError,
    NormalizationReport,
    NormalizationResult,
    Origin,
)
from .tabular import norm_key

_REQUIRED_APP_FIELDS = {"id", "name"}
_REQUIRED_CONNECTION_FIELDS = {"source_application_id", "target_application_id"}


def make_id(prefix: str, key: str) -> str:
    """Deterministic short id, e.g. 'APP-3F9A21C0'."""
    return f"{prefix}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:8].upper()}"


def _generated_app_id(source_system: str, source_id: str | None, name: str) -> str:
    if source_id:
        return make_id("APP", f"{source_system}:{source_id}")
    return make_id("APP", f"name:{norm_key(name)}")


# Merging

@dataclass
class _MergedApp:
    name: str
    origin: Origin
    source_system: SourceSystem
    source_id: str | None = None
    explicit_id: str | None = None
    aliases: set[str] = field(default_factory=set)
    external_ids: set[str] = field(default_factory=set)
    values: dict[str, FieldValue] = field(default_factory=dict)
    extra: dict[str, str | list[str]] = field(default_factory=dict)
    placeholder: bool = False
    id: str = ""


@dataclass
class _MergedConnection:
    origin: Origin
    source_system: SourceSystem
    name: str | None = None
    source_id: str | None = None
    interface_code: str | None = None
    external_ids: set[str] = field(default_factory=set)
    consumers: list[Ref] = field(default_factory=list)
    providers: list[Ref] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.interface_code or self.name or self.origin.describe()


def _app_keys(raw: RawApplication) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    if raw.explicit_id:
        keys.append(("id", f"id:{raw.explicit_id}"))
    if raw.source_id:
        keys.append(("source id", f"src:{raw.source_system}:{raw.source_id}"))
    keys.append(("id", f"id:{_generated_app_id(raw.source_system, raw.source_id, raw.name)}"))
    keys += [("external id", f"ext:{e}") for e in sorted(raw.external_ids)]
    keys += [("name", f"name:{a}") for a in sorted(raw.aliases | {norm_key(raw.name)})]
    return keys


def _connection_keys(raw: RawConnection) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    if raw.source_id:
        keys.append(("source id", f"src:{raw.source_system}:{raw.source_id}"))
    keys += [("external id", f"ext:{e}") for e in sorted(raw.external_ids)]
    if raw.interface_code:
        keys.append(("interface code", f"code:{norm_key(raw.interface_code)}"))
    if raw.name:
        keys.append(("name", f"name:{norm_key(raw.name)}"))
    return keys


def _merge_values(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    """Later non-empty values win; lifecycle dates merge phase by phase."""
    for key, new in incoming.items():
        if key == "lifecycle_dates" and key in target:
            old = target[key]
            if isinstance(new, FieldValue) and isinstance(old, FieldValue):
                target[key] = FieldValue(
                    {**old.value, **new.value}, new.system, new.origin, new.column, new.note
                )
            else:
                target[key] = {**old, **new}
        else:
            target[key] = new


def _merge_records(
    records: Iterable[Any],
    keys_of: Any,
    create: Any,
    absorb: Any,
    describe: Any,
    issues: list[Issue],
) -> list[Any]:
    merged: list[Any] = []
    index: dict[str, int] = {}
    for raw in records:
        keys = keys_of(raw)
        matches: list[tuple[int, str]] = []
        for label, key in keys:
            position = index.get(key)
            if position is not None and all(position != m for m, _ in matches):
                matches.append((position, label))
        if not matches:
            merged.append(create(raw))
            position = len(merged) - 1
        else:
            position, label = matches[0]
            earlier = merged[position]
            absorb(earlier, raw)
            issues.append(Issue.at(
                raw.origin, "info", "merged_record",
                f"Merged {describe(raw)} into the earlier record from "
                f"{earlier.origin.describe()} (matched on {label}).",
            ))
            if len(matches) > 1:
                others = ", ".join(merged[m].origin.describe() for m, _ in matches[1:])
                issues.append(Issue.at(
                    raw.origin, "warning", "ambiguous_match",
                    f"{describe(raw)} also matches records from {others}; "
                    "only the first match was used.",
                ))
        for _, key in keys:
            index.setdefault(key, position)
    return merged


def _create_app(raw: RawApplication) -> _MergedApp:
    return _MergedApp(
        name=raw.name,
        origin=raw.origin,
        source_system=raw.source_system,
        source_id=raw.source_id,
        explicit_id=raw.explicit_id,
        aliases=set(raw.aliases) | {norm_key(raw.name)},
        external_ids=set(raw.external_ids),
        values=dict(raw.values),
        extra=dict(raw.extra),
    )


def _absorb_app(target: _MergedApp, raw: RawApplication) -> None:
    target.name = raw.name
    target.aliases |= raw.aliases | {norm_key(raw.name)}
    target.external_ids |= raw.external_ids
    if raw.source_id and not target.source_id and raw.source_system == target.source_system:
        target.source_id = raw.source_id
    if raw.explicit_id and not target.explicit_id:
        target.explicit_id = raw.explicit_id
    _merge_values(target.values, raw.values)
    target.extra.update(raw.extra)


def _create_connection(raw: RawConnection) -> _MergedConnection:
    return _MergedConnection(
        origin=raw.origin,
        source_system=raw.source_system,
        name=raw.name,
        source_id=raw.source_id,
        interface_code=raw.interface_code,
        external_ids=set(raw.external_ids),
        consumers=list(raw.consumers),
        providers=list(raw.providers),
        values=dict(raw.values),
    )


def _absorb_connection(target: _MergedConnection, raw: RawConnection) -> None:
    if raw.name:
        target.name = raw.name
    if raw.source_id and not target.source_id and raw.source_system == target.source_system:
        target.source_id = raw.source_id
    if raw.interface_code and not target.interface_code:
        target.interface_code = raw.interface_code
    target.external_ids |= raw.external_ids
    if raw.consumers:
        target.consumers = list(raw.consumers)
    if raw.providers:
        target.providers = list(raw.providers)
    _merge_values(target.values, raw.values)


# Validation helper

def _build_model(
    model: type[BaseModel],
    kwargs: dict[str, Any],
    required: set[str],
    label: str,
    origin_of: Any,
    issues: list[Issue],
) -> Any:
    """
    Build `model`, dropping optional fields that fail validation.

    Returns None when a required field is invalid. Every dropped value is
    reported with its location and the allowed values from the validator.
    """
    while True:
        try:
            return model(**kwargs)
        except ValidationError as exc:
            dropped = False
            for error in exc.errors():
                field_name = str(error["loc"][0]) if error["loc"] else ""
                origin, column = origin_of(field_name)
                if field_name in required or field_name not in kwargs:
                    issues.append(Issue.at(
                        origin, "error", "invalid_record",
                        f"{label}: {field_name or 'record'} is invalid ({error['msg']}); "
                        "the record was skipped.",
                        column=column,
                    ))
                    return None
                issues.append(Issue.at(
                    origin, "error", "invalid_value",
                    f"{label}: invalid value {error.get('input')!r} for {field_name} "
                    f"({error['msg']}); the field was left empty.",
                    column=column,
                ))
                kwargs.pop(field_name, None)
                dropped = True
            if not dropped:
                return None


# Public API

def assemble(
    bundles: Sequence[RawBundle],
    as_of: date | None = None,
) -> NormalizationResult:
    """
    Merge, resolve, validate and report on raw records from one or more adapters.

    Bundles are applied in order, so later bundles (e.g. a filled-in CSV)
    override non-empty values from earlier ones (e.g. a LeanIX export).

    Raises:
        NormalizationError: if no applications remain after validation.
    """
    as_of = as_of or datetime.now(UTC).date()
    issues: list[Issue] = []
    report = NormalizationReport(
        source_systems=list(dict.fromkeys(b.source_system for b in bundles)),
        as_of=as_of,
    )
    for bundle in bundles:
        report.files.extend(bundle.files)
        issues.extend(bundle.issues)

    # 1. Merge
    apps: list[_MergedApp] = _merge_records(
        (a for b in bundles for a in b.applications),
        _app_keys, _create_app, _absorb_app,
        lambda r: f"application '{r.name}'",
        issues,
    )
    conns: list[_MergedConnection] = _merge_records(
        (c for b in bundles for c in b.connections),
        _connection_keys, _create_connection, _absorb_connection,
        lambda r: f"interface '{r.interface_code or r.name}'",
        issues,
    )

    # 2. Assign ids and index
    by_id: dict[str, _MergedApp] = {}
    by_name: dict[str, _MergedApp] = {}

    def register(app: _MergedApp) -> bool:
        if app.id in by_id:
            issues.append(Issue.at(
                app.origin, "error", "duplicate_application_id",
                f"Application '{app.name}' has the same id {app.id} as "
                f"'{by_id[app.id].name}'; it was skipped.",
            ))
            return False
        by_id[app.id] = app
        for alias in sorted(app.aliases):
            existing = by_name.setdefault(alias, app)
            if existing is not app:
                issues.append(Issue.at(
                    app.origin, "warning", "duplicate_application_name",
                    f"Applications '{existing.name}' and '{app.name}' share a name; "
                    "references by that name resolve to the first one.",
                ))
        return True

    registered: list[_MergedApp] = []
    for app in apps:
        app.id = app.explicit_id or _generated_app_id(app.source_system, app.source_id, app.name)
        if not app.explicit_id and not app.source_id:
            issues.append(Issue.at(
                app.origin, "info", "generated_id",
                f"Application '{app.name}' has no source id; its id {app.id} was "
                "generated from its name and changes if it is renamed.",
            ))
        if register(app):
            registered.append(app)

    def resolve(ref: Ref) -> _MergedApp | None:
        if ref.kind in ("id", "id_or_name") and ref.text in by_id:
            return by_id[ref.text]
        if ref.kind in ("name", "id_or_name"):
            return by_name.get(norm_key(ref.text))
        return None

    # 3. Resolve interfaces into connection drafts
    drafts: list[tuple[_MergedConnection, _MergedApp, _MergedApp]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for conn in conns:
        if not conn.consumers or not conn.providers:
            missing = " and ".join(
                side for side, refs in (("provider", conn.providers), ("consumer", conn.consumers))
                if not refs
            )
            report.incomplete_interfaces.append(conn.label)
            issues.append(Issue.at(
                conn.origin, "warning", "incomplete_interface",
                f"Interface '{conn.label}' has no {missing}; no connection was created.",
            ))
            continue

        endpoints: dict[str, list[_MergedApp]] = {"consumer": [], "provider": []}
        unresolved = False
        for side, refs in (("consumer", conn.consumers), ("provider", conn.providers)):
            for ref in refs:
                endpoint = resolve(ref)
                if endpoint is None and ref.kind == "name":
                    endpoint = _MergedApp(
                        name=ref.text,
                        origin=conn.origin,
                        source_system="placeholder",
                        aliases={norm_key(ref.text)},
                        placeholder=True,
                    )
                    endpoint.id = make_id("APP", f"name:{norm_key(ref.text)}")
                    if register(endpoint):
                        registered.append(endpoint)
                        report.placeholder_applications.append(ref.text)
                        issues.append(Issue.at(
                            conn.origin, "warning", "placeholder_application",
                            f"'{ref.text}' is referenced by interface '{conn.label}' but is "
                            "not in the import; created a placeholder application.",
                        ))
                if endpoint is None:
                    issues.append(Issue.at(
                        conn.origin, "error", "unknown_application",
                        f"Interface '{conn.label}' references unknown application "
                        f"'{ref.text}'; the connection was skipped.",
                    ))
                    unresolved = True
                else:
                    endpoints[side].append(endpoint)
        if unresolved:
            continue

        edge_key = conn.interface_code or conn.source_id or str(id(conn))
        for consumer in endpoints["consumer"]:
            for provider in endpoints["provider"]:
                if consumer.id == provider.id:
                    issues.append(Issue.at(
                        conn.origin, "warning", "self_connection",
                        f"Interface '{conn.label}' connects '{consumer.name}' to itself; "
                        "no connection was created.",
                    ))
                    continue
                key = (edge_key, consumer.id, provider.id)
                if key not in seen_edges:
                    seen_edges.add(key)
                    drafts.append((conn, consumer, provider))

    # 4. Component links and derived values
    for link in (link for b in bundles for link in b.component_links):
        target = resolve(link.application)
        if target is None:
            issues.append(Issue.at(
                link.origin, "warning", "unknown_component_application",
                f"IT component '{link.component}' is linked to unknown application "
                f"'{link.application.text}'; the link was ignored.",
            ))
            continue
        current = target.values.get("it_components")
        components = list(current.value) if current else []
        if link.component not in components:
            components.append(link.component)
        target.values["it_components"] = FieldValue(
            components, "leanix", link.origin, "relITComponentToApplication"
        )

    for app in registered:
        if "data_objects" not in app.values:
            objects: list[str] = []
            for conn, consumer, provider in drafts:
                if app in (consumer, provider):
                    for obj in conn.values.get("data_objects") or []:
                        if obj not in objects:
                            objects.append(obj)
            if objects:
                app.values["data_objects"] = FieldValue(
                    objects, app.source_system, note="derived from interface data objects"
                )
        hosting = app.values.get("hosting_type")
        if "deployment_environment" not in app.values and hosting is not None:
            environment = HOSTING_TO_DEPLOYMENT.get(hosting.value)
            if environment is not None:
                app.values["deployment_environment"] = FieldValue(
                    environment, hosting.system, note="derived from hosting_type"
                )
        dates = app.values.get("lifecycle_dates")
        if "lifecycle_status" not in app.values and dates is not None:
            status = derive_lifecycle_status(dates.value, as_of)
            if status is not None:
                app.values["lifecycle_status"] = FieldValue(
                    status, dates.system, note=f"derived from lifecycle dates as of {as_of}"
                )

    # 5. Validate applications
    applications: list[Application] = []
    valid_ids: set[str] = set()
    for app in registered:
        built = _build_application(app, issues)
        if built is not None:
            applications.append(built)
            valid_ids.add(built.id)

    connections: list[Connection] = []
    for conn, consumer, provider in drafts:
        if consumer.id not in valid_ids or provider.id not in valid_ids:
            continue
        built_conn = _build_connection(conn, consumer.id, provider.id, as_of, issues)
        if built_conn is not None:
            connections.append(built_conn)

    # 6. Report
    report.issues = issues
    report.application_count = len(applications)
    report.connection_count = len(connections)
    report.field_coverage = {
        name: sum(1 for a in applications if a.field_sources[name].kind != "missing")
        for name in TRACKED_FIELDS
    }
    report.missing_by_application = [
        ApplicationMissingData(
            application_id=a.id,
            application_name=a.name,
            placeholder=a.source_system == "placeholder",
            missing_fields=[n for n in TRACKED_FIELDS if a.field_sources[n].kind == "missing"],
        )
        for a in applications
    ]

    if not applications:
        report.issues.append(Issue(
            severity="error", code="no_applications", message="No applications found."
        ))
        raise NormalizationError("No applications found", report)

    architecture = EnterpriseArchitecture(applications=applications, connections=connections)
    return NormalizationResult(architecture=architecture, report=report)


def _has_value(value: Any) -> bool:
    return value is not None and value != [] and value != {}


def _build_application(app: _MergedApp, issues: list[Issue]) -> Application | None:
    kwargs: dict[str, Any] = {
        "id": app.id,
        "name": app.name,
        "source_system": app.source_system,
        "source_id": app.source_id,
        "extra_attributes": app.extra or None,
    }
    kwargs.update({k: fv.value for k, fv in app.values.items() if _has_value(fv.value)})

    def origin_of(field_name: str) -> tuple[Origin | None, str | None]:
        fv = app.values.get(field_name)
        if fv is not None and fv.origin is not None:
            return fv.origin, fv.column
        return app.origin, None

    # Validate first, then attach provenance for exactly the values that survived.
    validated = _build_model(
        Application, kwargs, _REQUIRED_APP_FIELDS, f"Application '{app.name}'", origin_of, issues
    )
    if validated is None:
        return None
    field_sources: dict[str, FieldSource] = {}
    for name in TRACKED_FIELDS:
        fv = app.values.get(name)
        if fv is not None and _has_value(getattr(validated, name)):
            field_sources[name] = FieldSource(kind="imported", system=fv.system, detail=fv.detail)
        else:
            field_sources[name] = FieldSource(kind="missing")
    return validated.model_copy(update={"field_sources": field_sources})


def _build_connection(
    conn: _MergedConnection,
    source_id: str,
    target_id: str,
    as_of: date,
    issues: list[Issue],
) -> Connection | None:
    values = {k: v for k, v in conn.values.items() if _has_value(v)}
    if "lifecycle_status" not in values and "lifecycle_dates" in values:
        status = derive_lifecycle_status(values["lifecycle_dates"], as_of)
        if status is not None:
            values["lifecycle_status"] = status
    kwargs: dict[str, Any] = {
        "source_application_id": source_id,
        "target_application_id": target_id,
        "relationship": values.pop("relationship", "Other"),
        "interface_id": conn.interface_code or conn.source_id,
        "name": conn.name,
        "source_system": conn.source_system,
        "source_id": conn.source_id,
        **values,
    }
    return _build_model(  # type: ignore[no-any-return]
        Connection, kwargs, _REQUIRED_CONNECTION_FIELDS | {"relationship"},
        f"Interface '{conn.label}'", lambda _f: (conn.origin, None), issues,
    )
