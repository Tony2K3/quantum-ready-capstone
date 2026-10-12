"""BlueDolphin — public REST API (ValueBlue)
    Base URL: https://public-api.{eu|us}.bluedolphin.app
    Headers:  x-api-key: <user API key>, tenant: <tenant name>
    Objects:  GET /v1/objects (list), GET /v1/objects/{id} (details incl.
              object_properties and related_objects)
    Rate limit: about one call per 250 ms per IP, so calls are paced.
"""

from __future__ import annotations

import asyncio
import os
import time

import httpx

from .. import config
from ..normalize import make_edge, normalize_attributes, text
from ..resilience import CircuitBreaker
from ..schema import Edge, HealthState, HealthStatus, Node
from . import samples

API_KEY = os.environ.get("BLUEDOLPHIN_API_KEY")
TENANT = os.environ.get("BLUEDOLPHIN_TENANT")
REGION = os.environ.get("BLUEDOLPHIN_REGION", "eu")
BASE_URL = f"https://public-api.{REGION}.bluedolphin.app"
MOCK = not (API_KEY and TENANT)

# BlueDolphin object type names (lower-case) for each node type. These are
# ArchiMate defaults; tenants can rename them, so add names here if needed.
TYPE_MAP = {
    "application": ["application", "application component"],
    "data_object": ["data object", "business object"],
    "interface": ["application interface", "interface"],
    "it_component": ["node", "system software", "technology service", "device",
                     "it component", "technology component"],
    "business_capability": ["capability", "business capability"],
    "provider": ["provider", "vendor", "supplier"],
}

_PAGE_SIZE = 100
_MIN_INTERVAL = 0.26  # seconds between calls

_client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
breaker = CircuitBreaker()
_last_call = 0.0
_cache: tuple[float, tuple[list[Node], list[Edge]]] | None = None


def _headers() -> dict:
    return {
        "x-api-key": API_KEY or "",
        "tenant": TENANT or "",
        "Accept": "application/json",
    }


async def _get(path: str, params: dict | None = None):
    """GET with rate-limit pacing and one retry on 429. Unwraps a
    {"data": ...} envelope if present."""
    global _last_call
    for attempt in range(2):
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()
        resp = await _client.get(path, headers=_headers(), params=params)
        if resp.status_code == 429 and attempt == 0:
            await asyncio.sleep(1.0)
            continue
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and body.get("data") is not None:
            return body["data"]
        return body
    resp.raise_for_status()


def _items(body) -> list[dict]:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("items", "objects", "value", "results"):
            if isinstance(body.get(key), list):
                return body[key]
    return []


def _type_name(obj: dict) -> str:
    t = obj.get("type") or obj.get("object_type") or obj.get("definition") or {}
    if isinstance(t, dict):
        return t.get("name") or t.get("name_internal") or ""
    return str(t)


def _node_type(obj: dict) -> str | None:
    name = _type_name(obj).strip().lower()
    for node_type, names in TYPE_MAP.items():
        if name in names:
            return node_type
    return None


def _raw_properties(obj: dict) -> dict:
    """object_properties can be a list of {name, value} or a plain dict."""
    props = obj.get("object_properties") or obj.get("properties") or {}
    if isinstance(props, dict):
        return dict(props)
    out = {}
    for p in props:
        if isinstance(p, dict) and p.get("name"):
            out[p["name"]] = p.get("value")
    return out


def _relation_parts(rel) -> tuple[str | None, str, str]:
    """Pull (target_id, relationship_label, direction) out of one
    related_objects entry. The layout isn't documented publicly, so this
    handles the likely shapes; see the README's first-live-run notes."""
    if not isinstance(rel, dict):
        return None, "", ""
    target = rel.get("object") or rel.get("related_object") or rel.get("target") or {}
    target_id = (
        rel.get("object_id") or rel.get("related_object_id") or rel.get("target_id")
        or (target.get("id") if isinstance(target, dict) else None) or rel.get("id")
    )
    label = text(
        rel.get("relationship_type") or rel.get("relation_type") or rel.get("relationship")
        or rel.get("relation_name") or rel.get("name") or rel.get("type") or ""
    )
    direction = str(rel.get("direction") or "").lower()
    return (str(target_id) if target_id else None), label, direction


def to_topology(objects: list[dict]) -> tuple[list[Node], list[Edge]]:
    by_id: dict[str, Node] = {}
    for obj in objects:
        node_type = _node_type(obj)
        if not node_type or obj.get("id") is None:
            continue
        attrs = normalize_attributes(_raw_properties(obj))
        attrs["status"] = attrs["status"] or text(obj.get("status"))
        attrs["workspace"] = attrs["workspace"] or text(obj.get("workspace"))
        attrs["business_unit"] = attrs["business_unit"] or attrs["workspace"]
        attrs["description"] = attrs["description"] or text(obj.get("description"))
        node = Node(
            id=f"bd:{obj['id']}", source="bluedolphin", node_type=node_type,
            name=obj.get("object_title") or obj.get("title") or obj.get("name") or "",
            attributes=attrs,
        )
        by_id[str(obj["id"])] = node

    edges: dict[str, Edge] = {}
    for obj in objects:
        here = by_id.get(str(obj.get("id")))
        if not here:
            continue
        for rel in obj.get("related_objects") or []:
            target_id, label, direction = _relation_parts(rel)
            there = by_id.get(target_id) if target_id else None
            if not there or there.id == here.id:
                continue
            a, b = (there, here) if direction.startswith("in") else (here, there)
            # ArchiMate "serving": X serves Y means Y depends on X.
            if a.node_type == b.node_type and ("serv" in label.lower() or "used by" in label.lower()):
                a, b = b, a
            edge = make_edge("bluedolphin", a, b, label)
            edges[edge.id] = edge  # both ends list the relation; keep one

    return list(by_id.values()), list(edges.values())


async def _pull_objects() -> list[dict]:
    if MOCK:
        return samples.bluedolphin_objects()

    wanted: list[dict] = []
    skip = 0
    while True:
        page = _items(await _get("/v1/objects", {"take": _PAGE_SIZE, "skip": skip}))
        if not page:
            break
        # TODO: filter server-side once the tenant's options are known, so
        # large tenants don't have to page through every object.
        wanted.extend(o for o in page if _node_type(o))
        if len(page) < _PAGE_SIZE:
            break
        skip += _PAGE_SIZE

    detailed = []
    for obj in wanted:
        if obj.get("object_properties") is None or obj.get("related_objects") is None:
            full = await _get(f"/v1/objects/{obj['id']}")
            if isinstance(full, dict):
                obj = {**obj, **full}
        detailed.append(obj)
    return detailed


async def topology() -> tuple[list[Node], list[Edge]]:
    global _cache
    if _cache and time.monotonic() - _cache[0] < config.CACHE_SECONDS:
        return _cache[1]
    result = to_topology(await _pull_objects())
    _cache = (time.monotonic(), result)
    return result


async def health() -> HealthStatus:
    if MOCK:
        return HealthStatus(source="bluedolphin", state=HealthState.HEALTHY, detail="sample data")
    try:
        await _get("/v1/objects", {"take": 1})
        return HealthStatus(source="bluedolphin", state=HealthState.HEALTHY)
    except Exception as exc:  # noqa: BLE001
        return HealthStatus(source="bluedolphin", state=HealthState.DOWN, detail=str(exc))
