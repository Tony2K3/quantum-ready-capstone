"""CSV export: one file per entity type, plus every edge in
relationships.csv."""

from __future__ import annotations

import csv
import json
import os

from .applications import APPLICATION_EXTRA_FIELDS, application_records, join, linked_nodes
from .schema import APPLICATION_FIELDS, ATTR_KEYS, Edge, Node


def build_csv_tables(nodes: list[Node], edges: list[Edge]) -> dict[str, tuple[list[str], list[dict]]]:
    """{filename: (columns, rows)} for every CSV the export writes."""
    by_id = {n.id: n for n in nodes}
    name = lambda node_id: by_id[node_id].name if node_id in by_id else node_id  # noqa: E731

    def linked(node_id: str, edge_types: tuple[str, ...], outgoing: bool) -> str:
        """Names of nodes connected to node_id by the given edge types."""
        return join(n.name for n in linked_nodes(edges, by_id, node_id, edge_types, outgoing))

    def base(n: Node) -> dict:
        a = n.attributes
        return {
            "id": n.id, "source": n.source, "name": n.name,
            **{k: a.get(k, "") for k in ATTR_KEYS},
            "other_properties": json.dumps(a.get("other_properties") or {}, ensure_ascii=False),
        }

    def of_type(t: str) -> list[Node]:
        return sorted((n for n in nodes if n.node_type == t), key=lambda n: (n.source, n.name))

    tables: dict[str, tuple[list[str], list[dict]]] = {}

    tables["applications.csv"] = (
        [*APPLICATION_FIELDS, *APPLICATION_EXTRA_FIELDS], application_records(nodes, edges)
    )

    deps = [
        {"source": e.source, "from_id": e.from_node_id, "from_name": name(e.from_node_id),
         "depends_on_id": e.to_node_id, "depends_on_name": name(e.to_node_id),
         "from_type": by_id[e.from_node_id].node_type, "source_relationship": e.label}
        for e in edges if e.edge_type == "depends_on"
    ]
    tables["dependencies.csv"] = ([
        "source", "from_id", "from_name", "depends_on_id", "depends_on_name", "from_type",
        "source_relationship",
    ], deps)

    data_objects = []
    for n in of_type("data_object"):
        row = base(n)
        row["used_by_apps"] = linked(n.id, ("uses_data",), False)
        row["carried_by_interfaces"] = linked(n.id, ("carries_data",), False)
        data_objects.append(row)
    tables["data_objects.csv"] = ([
        "id", "source", "name", "sensitivity", "retention", "owner", "lifecycle", "used_by_apps",
        "carried_by_interfaces", "description", "other_properties",
    ], data_objects)

    interfaces = []
    for n in of_type("interface"):
        row = base(n)
        row["provider_apps"] = linked(n.id, ("provides_interface",), False)
        row["consumer_apps"] = linked(n.id, ("consumes_interface",), False)
        row["connected_apps"] = linked(n.id, ("connects_interface",), False)
        row["data_carried"] = linked(n.id, ("carries_data",), True)
        interfaces.append(row)
    tables["interfaces.csv"] = ([
        "id", "source", "name", "provider_apps", "consumer_apps", "connected_apps",
        "data_carried", "protocols", "lifecycle", "description", "other_properties",
    ], interfaces)

    components = []
    for n in of_type("it_component"):
        row = base(n)
        row["vendor"] = row["vendor"] or linked(n.id, ("supplied_by",), True)
        row["used_by_apps"] = linked(n.id, ("runs_on",), False)
        components.append(row)
    tables["it_components.csv"] = ([
        "id", "source", "name", "category", "lifecycle", "end_of_life", "vendor",
        "used_by_apps", "description", "other_properties",
    ], components)

    capabilities = []
    for n in of_type("business_capability"):
        row = base(n)
        row["supported_by_apps"] = linked(n.id, ("supports",), False)
        capabilities.append(row)
    tables["business_capabilities.csv"] = ([
        "id", "source", "name", "supported_by_apps", "description", "other_properties",
    ], capabilities)

    rels = [
        {"source": e.source, "relationship": e.edge_type,
         "from_id": e.from_node_id, "from_name": name(e.from_node_id),
         "from_type": by_id[e.from_node_id].node_type,
         "to_id": e.to_node_id, "to_name": name(e.to_node_id),
         "to_type": by_id[e.to_node_id].node_type, "source_relationship": e.label}
        for e in edges
    ]
    tables["relationships.csv"] = ([
        "source", "relationship", "from_id", "from_name", "from_type", "to_id", "to_name",
        "to_type", "source_relationship",
    ], rels)

    return tables


def _write_csv(path: str, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_csvs(nodes: list[Node], edges: list[Edge], out_dir: str) -> dict:
    """Write every table into out_dir (created if needed).
    Returns {filename: {"path", "rows"}}."""
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for filename, (columns, rows) in build_csv_tables(nodes, edges).items():
        path = os.path.join(out_dir, filename)
        _write_csv(path, columns, rows)
        files[filename] = {"path": path, "rows": len(rows)}
    return files
