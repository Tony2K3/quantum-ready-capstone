"""The MCP tools this server exposes."""

from __future__ import annotations

import asyncio
import dataclasses
import os

from mcp.server.fastmcp import FastMCP

from .applications import application_records
from .export import write_csvs
from .schema import APPLICATION_FIELDS
from .sources import bluedolphin, leanix
from .topology import all_topology, status

mcp = FastMCP("decision-cortex-connectors")


@mcp.tool()
async def fetch_nodes(node_type: str | None = None) -> dict:
    """Fetch nodes from BlueDolphin and LeanIX in one normalized shape.
    node_type (optional): application, data_object, interface, it_component,
    business_capability or provider. If a source is down, its nodes are
    missing and sources_failed says why."""
    topo = await all_topology()
    nodes = [n for n in topo["nodes"] if node_type is None or n.node_type == node_type]
    return {
        "nodes": [dataclasses.asdict(n) for n in nodes],
        "count": len(nodes),
        **status(topo),
    }


@mcp.tool()
async def fetch_applications() -> dict:
    """Applications from both sources in Peter's Application schema (the
    roadmap generator's input): id, name, description, business_unit, owner,
    business_criticality, data_sensitivity, data_longevity, vendor_dependency,
    tech_stack, deployment_environment, migration_complexity, cryptography,
    pqc_readiness, network_protocols, network_exposure, crypto_agility,
    key_management_type. Crypto fields stay empty while
    INCLUDE_CRYPTO_FIELDS is off."""
    topo = await all_topology()
    records = application_records(topo["nodes"], topo["edges"])
    return {
        "applications": [{k: r[k] for k in APPLICATION_FIELDS} for r in records],
        "count": len(records),
        **status(topo),
    }


@mcp.tool()
async def fetch_edges(edge_type: str | None = None) -> dict:
    """Fetch relationships between nodes from both sources.
    edge_type (optional): depends_on, uses_data, runs_on, supports,
    provides_interface, consumes_interface, connects_interface,
    carries_data, supplied_by or related_to."""
    topo = await all_topology()
    edges = [e for e in topo["edges"] if edge_type is None or e.edge_type == edge_type]
    return {
        "edges": [dataclasses.asdict(e) for e in edges],
        "count": len(edges),
        **status(topo),
    }


@mcp.tool()
async def health_check() -> list[dict]:
    """Whether BlueDolphin and LeanIX are currently answering."""
    statuses = await asyncio.gather(bluedolphin.health(), leanix.health())
    return [dataclasses.asdict(s) for s in statuses]


@mcp.tool()
async def export_csv(output_dir: str = "export") -> dict:
    """Pull everything from both sources and write one CSV per entity type
    into output_dir: applications, dependencies, data_objects, interfaces,
    it_components, business_capabilities, and relationships (all edges)."""
    topo = await all_topology()
    out = os.path.abspath(output_dir)
    files = write_csvs(topo["nodes"], topo["edges"], out)
    return {
        "ok": bool(topo["sources_ok"]),
        "output_dir": out,
        "files": files,
        **status(topo),
    }
