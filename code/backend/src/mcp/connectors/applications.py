"""Builds Peter's Application records (the roadmap generator's input) from
the merged topology."""

from __future__ import annotations

import json

from .schema import Edge, Node

# Ordering used to pick the most sensitive data an application touches.
_SENSITIVITY_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3,
                     "secret": 4, "strictly confidential": 4}

# Columns added after Peter's fields in applications.csv (useful context
# the roadmap generator can ignore if it doesn't need it).
APPLICATION_EXTRA_FIELDS = (
    "source", "status", "lifecycle", "end_of_life", "depends_on", "needed_by",
    "data_objects", "business_capabilities", "other_properties",
)


def linked_nodes(edges: list[Edge], by_id: dict[str, Node], node_id: str,
                 edge_types: tuple[str, ...], outgoing: bool) -> list[Node]:
    """Nodes connected to node_id by the given edge types, in one direction."""
    found: dict[str, Node] = {}
    for e in edges:
        if e.edge_type not in edge_types:
            continue
        other = e.to_node_id if outgoing and e.from_node_id == node_id else (
            e.from_node_id if not outgoing and e.to_node_id == node_id else None)
        if other in by_id:
            found[other] = by_id[other]
    return sorted(found.values(), key=lambda n: n.name)


def join(values) -> str:
    """Join non-empty values with '; ', keeping order and dropping repeats."""
    seen: list[str] = []
    for v in values:
        for part in str(v or "").split("; "):
            if part and part not in seen:
                seen.append(part)
    return "; ".join(seen)


def most_sensitive(values: list[str]) -> str:
    values = [v for v in values if v]
    if not values:
        return ""
    return max(values, key=lambda v: _SENSITIVITY_RANK.get(v.strip().lower(), -1))


def application_records(nodes: list[Node], edges: list[Edge]) -> list[dict]:
    """One record per application in Peter's Application schema, plus the
    extra context columns. Fields an app doesn't set directly are derived
    from what it's connected to:
        data_sensitivity   most sensitive data object the app uses
        data_longevity     retention of the data objects the app uses
        vendor_dependency  app vendor + providers + vendors of its tech stack
        tech_stack         IT components the app runs on
        network_protocols  app's own protocols + those of its interfaces
    """
    by_id = {n.id: n for n in nodes}

    def linked(node_id, edge_types, outgoing=True):
        return linked_nodes(edges, by_id, node_id, edge_types, outgoing)

    records = []
    apps = sorted((n for n in nodes if n.node_type == "application"), key=lambda n: (n.source, n.name))
    for app in apps:
        a = app.attributes
        data = linked(app.id, ("uses_data",))
        stack = linked(app.id, ("runs_on",))
        interfaces = linked(app.id, ("provides_interface", "consumes_interface", "connects_interface"))
        providers = linked(app.id, ("supplied_by",))
        stack_vendors = [c.attributes.get("vendor") or join(p.name for p in linked(c.id, ("supplied_by",)))
                         for c in stack]

        records.append({
            "id": app.id,
            "name": app.name,
            "description": a.get("description", ""),
            "business_unit": a.get("business_unit", ""),
            "owner": a.get("owner", ""),
            "business_criticality": a.get("criticality", ""),
            "data_sensitivity": a.get("sensitivity") or most_sensitive(
                [d.attributes.get("sensitivity", "") for d in data]),
            "data_longevity": a.get("retention") or join(
                f"{d.name}: {d.attributes['retention']}" for d in data if d.attributes.get("retention")),
            "vendor_dependency": join([a.get("vendor"), *(p.name for p in providers), *stack_vendors]),
            "tech_stack": join(c.name for c in stack),
            "deployment_environment": a.get("hosting", ""),
            "migration_complexity": a.get("migration_complexity", ""),
            "cryptography": a.get("cryptography", ""),
            "pqc_readiness": a.get("pqc_readiness", ""),
            "network_protocols": join([a.get("protocols"), *(i.attributes.get("protocols") for i in interfaces)]),
            "network_exposure": a.get("network_exposure", ""),
            "crypto_agility": a.get("crypto_agility", ""),
            "key_management_type": a.get("key_management_type", ""),
            # extra context
            "source": app.source,
            "status": a.get("status", ""),
            "lifecycle": a.get("lifecycle", ""),
            "end_of_life": a.get("end_of_life", ""),
            "depends_on": join(n.name for n in linked(app.id, ("depends_on",))),
            "needed_by": join(n.name for n in linked(app.id, ("depends_on",), outgoing=False)),
            "data_objects": join(d.name for d in data),
            "business_capabilities": join(c.name for c in linked(app.id, ("supports",))),
            "other_properties": json.dumps(a.get("other_properties") or {}, ensure_ascii=False),
        })
    return records
