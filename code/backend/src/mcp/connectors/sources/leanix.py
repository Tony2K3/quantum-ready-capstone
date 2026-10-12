"""LeanIX — GraphQL (Pathfinder API)
    Auth:   POST https://{host}/services/mtm/v1/oauth2/token
            basic auth "apitoken:<token>", grant_type=client_credentials
    Data:   POST https://{host}/services/pathfinder/v1/graphql
"""

from __future__ import annotations

import os
import time

import httpx

from .. import config
from ..normalize import make_edge, normalize_attributes
from ..resilience import CircuitBreaker
from ..schema import Edge, HealthState, HealthStatus, Node
from . import samples

API_TOKEN = os.environ.get("LEANIX_API_TOKEN")
HOST = os.environ.get("LEANIX_HOST")
MOCK = not (API_TOKEN and HOST)
BASE_URL = f"https://{HOST or 'app.leanix.net'}"

_PAGE_SIZE = 100
_client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
breaker = CircuitBreaker()
_token: tuple[float, str] | None = None
_cache: tuple[float, tuple[list[Node], list[Edge]]] | None = None

# LeanIX fact sheet type -> our node type
TYPE_MAP = {
    "Application": "application",
    "DataObject": "data_object",
    "Interface": "interface",
    "ITComponent": "it_component",
    "BusinessCapability": "business_capability",
    "Provider": "provider",
}

# LeanIX relation field -> edge type (from = the fact sheet holding it)
RELATIONS = {
    "relToRequires": "depends_on",
    "relApplicationToDataObject": "uses_data",
    "relApplicationToITComponent": "runs_on",
    "relApplicationToBusinessCapability": "supports",
    "relProviderApplicationToInterface": "provides_interface",
    "relConsumerApplicationToInterface": "consumes_interface",
    "relInterfaceToDataObject": "carries_data",
    "relITComponentToProvider": "supplied_by",
}


def _rel(name: str) -> str:
    return f"{name} {{ edges {{ node {{ factSheet {{ id }} }} }} }}"


_COMMON_FIELDS = (
    "id name type description "
    "lifecycle { asString phases { phase startDate } } "
    "tags { name tagGroup { name } } "
    "subscriptions { edges { node { type user { email } } } }"
)

# Extra fields per fact sheet type. TODO: confirm against the customer's
# meta model on the first live run (see README).
TYPE_FIELDS = {
    "Application": "businessCriticality " + " ".join(_rel(r) for r in (
        "relToRequires", "relApplicationToDataObject", "relApplicationToITComponent",
        "relApplicationToBusinessCapability", "relProviderApplicationToInterface",
        "relConsumerApplicationToInterface")),
    "DataObject": "dataClassification",
    "Interface": _rel("relInterfaceToDataObject"),
    "ITComponent": "category " + _rel("relITComponentToProvider") + " " + _rel("relToRequires"),
    "BusinessCapability": "",
    "Provider": "",
}


def _query(fs_type: str) -> str:
    extra = TYPE_FIELDS.get(fs_type, "")
    fragment = f"... on {fs_type} {{ {extra} }}" if extra else ""
    return (
        "query($cursor: String) { allFactSheets(first: %d, after: $cursor, "
        'filter: {facetFilters: [{facetKey: "FactSheetTypes", keys: ["%s"]}]}) '
        "{ pageInfo { hasNextPage endCursor } edges { node { %s %s } } } }"
        % (_PAGE_SIZE, fs_type, _COMMON_FIELDS, fragment)
    )


async def _authenticate() -> str:
    global _token
    if _token and time.monotonic() < _token[0]:
        return _token[1]
    resp = await _client.post(
        "/services/mtm/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=("apitoken", API_TOKEN or ""),
    )
    resp.raise_for_status()
    body = resp.json()
    lifetime = float(body.get("expires_in", 3600))
    _token = (time.monotonic() + lifetime - 60, body["access_token"])
    return _token[1]


async def _graphql(query: str, variables: dict) -> dict:
    token = await _authenticate()
    resp = await _client.post(
        "/services/pathfinder/v1/graphql",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"LeanIX GraphQL error: {body['errors'][0].get('message', body['errors'])}")
    return body["data"]


async def _pull_fact_sheets() -> list[dict]:
    if MOCK:
        return samples.leanix_fact_sheets()

    sheets: list[dict] = []
    for fs_type in TYPE_MAP:
        cursor = None
        query = _query(fs_type)
        while True:
            data = await _graphql(query, {"cursor": cursor})
            page = data["allFactSheets"]
            sheets.extend(e["node"] for e in page["edges"])
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]
    return sheets


def _rel_ids(sheet: dict, rel_name: str) -> list[str]:
    rel = sheet.get(rel_name) or {}
    ids = []
    for edge in rel.get("edges") or []:
        fs = (edge.get("node") or {}).get("factSheet") or {}
        if fs.get("id"):
            ids.append(fs["id"])
    return ids


def to_topology(sheets: list[dict]) -> tuple[list[Node], list[Edge]]:
    by_id: dict[str, Node] = {}
    for s in sheets:
        node_type = TYPE_MAP.get(s.get("type", ""))
        if not node_type or not s.get("id"):
            continue

        raw: dict = {}
        if s.get("description"):
            raw["description"] = s["description"]
        lifecycle = s.get("lifecycle") or {}
        if lifecycle.get("asString"):
            raw["lifecycle"] = lifecycle["asString"]
        for phase in lifecycle.get("phases") or []:
            if phase.get("phase") == "endOfLife":
                raw["end of life"] = phase.get("startDate")
        if s.get("businessCriticality"):
            raw["business criticality"] = s["businessCriticality"]
        if s.get("dataClassification"):
            raw["data classification"] = s["dataClassification"]
        if s.get("category"):
            raw["category"] = s["category"]
        owners = [
            (e.get("node") or {}).get("user", {}).get("email")
            for e in (s.get("subscriptions") or {}).get("edges") or []
            if (e.get("node") or {}).get("type") in ("RESPONSIBLE", "ACCOUNTABLE")
        ]
        if any(owners):
            raw["owner"] = "; ".join(o for o in owners if o)
        for tag in s.get("tags") or []:
            group = ((tag.get("tagGroup") or {}).get("name") or "Tag").strip()
            key = "hosting" if "host" in group.lower() else group
            raw[key] = f"{raw[key]}; {tag['name']}" if raw.get(key) else tag.get("name")

        by_id[s["id"]] = Node(
            id=f"lx:{s['id']}", source="leanix", node_type=node_type,
            name=s.get("name") or "", attributes=normalize_attributes(raw),
        )

    edges: dict[str, Edge] = {}
    for s in sheets:
        here = by_id.get(s.get("id"))
        if not here:
            continue
        for rel_name, edge_type in RELATIONS.items():
            for target_id in _rel_ids(s, rel_name):
                there = by_id.get(target_id)
                if there and there.id != here.id:
                    edge = make_edge("leanix", here, there, rel_name, edge_type)
                    edges[edge.id] = edge

    return list(by_id.values()), list(edges.values())


async def topology() -> tuple[list[Node], list[Edge]]:
    global _cache
    if _cache and time.monotonic() - _cache[0] < config.CACHE_SECONDS:
        return _cache[1]
    result = to_topology(await _pull_fact_sheets())
    _cache = (time.monotonic(), result)
    return result


async def health() -> HealthStatus:
    if MOCK:
        return HealthStatus(source="leanix", state=HealthState.HEALTHY, detail="sample data")
    try:
        await _authenticate()
        return HealthStatus(source="leanix", state=HealthState.HEALTHY)
    except Exception as exc:  # noqa: BLE001
        return HealthStatus(source="leanix", state=HealthState.DOWN, detail=str(exc))
