import asyncio

import httpx
import pytest

from connectors.sources import bluedolphin, samples
from helpers import by_name, edge_between, instant_sleep


# --- parsing ------------------------------------------------------------------

def test_bluedolphin_sample_has_every_node_type():
    nodes, _ = bluedolphin.to_topology(samples.bluedolphin_objects())
    types = {n.node_type for n in nodes}
    assert {"application", "data_object", "interface", "it_component", "business_capability"} <= types


def test_bluedolphin_serving_relation_points_dependency_the_right_way():
    # Payments Gateway "serves" Order Service -> Order Service depends on Payments Gateway
    nodes, edges = bluedolphin.to_topology(samples.bluedolphin_objects())
    deps = edge_between(edges, nodes, "Order Service", "Payments Gateway")
    assert [e.edge_type for e in deps] == ["depends_on"]
    assert not edge_between(edges, nodes, "Payments Gateway", "Order Service")


def test_bluedolphin_edge_types_inferred_from_node_types():
    nodes, edges = bluedolphin.to_topology(samples.bluedolphin_objects())
    assert edge_between(edges, nodes, "Order Service", "Customer Record")[0].edge_type == "uses_data"
    assert edge_between(edges, nodes, "Order Service", "PostgreSQL 14")[0].edge_type == "runs_on"
    assert edge_between(edges, nodes, "Order Service", "Order Management")[0].edge_type == "supports"


def test_bluedolphin_relation_listed_on_both_ends_is_not_duplicated():
    objs = [
        {"id": "a", "object_title": "A", "type": {"name": "Application"},
         "related_objects": [{"object_id": "b", "relationship_type": "Flow", "direction": "outgoing"}]},
        {"id": "b", "object_title": "B", "type": {"name": "Application"},
         "related_objects": [{"object_id": "a", "relationship_type": "Flow", "direction": "incoming"}]},
    ]
    _, edges = bluedolphin.to_topology(objs)
    assert len(edges) == 1


@pytest.mark.parametrize("rel", [
    {"object_id": "b", "relationship_type": "Flow"},
    {"object": {"id": "b"}, "relation_type": {"name": "Flow"}},
    {"related_object_id": "b", "relationship": "Flow"},
])
def test_bluedolphin_relation_layout_variants(rel):
    objs = [
        {"id": "a", "object_title": "A", "type": {"name": "Application"}, "related_objects": [rel]},
        {"id": "b", "object_title": "B", "type": {"name": "Application"}},
    ]
    _, edges = bluedolphin.to_topology(objs)
    assert [(e.from_node_id, e.to_node_id) for e in edges] == [("bd:a", "bd:b")]


def test_bluedolphin_ignores_types_it_does_not_know():
    objs = [{"id": "x", "object_title": "Some Goal", "type": {"name": "Goal"}}]
    nodes, _ = bluedolphin.to_topology(objs)
    assert nodes == []


def test_bluedolphin_workspace_used_as_business_unit_fallback():
    nodes, _ = bluedolphin.to_topology(samples.bluedolphin_objects())
    assert by_name(nodes, "Payments Gateway").attributes["business_unit"] == "Finance"


# --- live code paths against a fake API ----------------------------------------

async def test_bluedolphin_live_requests(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/objects":
            skip = int(request.url.params.get("skip", 0))
            page = [{"id": f"o{i}", "object_title": f"Obj {i}",
                     "type": {"name": "Application" if i % 2 == 0 else "Goal"}}
                    for i in range(skip, min(skip + 100, 150))]
            return httpx.Response(200, json={"items": page})
        oid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"data": {
            "id": oid, "object_title": f"App {oid}", "type": {"name": "Application"},
            "object_properties": [{"name": "Business Criticality", "value": "High"}],
            "related_objects": [],
        }})

    monkeypatch.setattr(bluedolphin, "MOCK", False)
    monkeypatch.setattr(bluedolphin, "API_KEY", "key-123")
    monkeypatch.setattr(bluedolphin, "TENANT", "contoso")
    monkeypatch.setattr(bluedolphin, "_client", httpx.AsyncClient(
        base_url="https://public-api.eu.bluedolphin.app", transport=httpx.MockTransport(handler)))

    nodes, _ = await bluedolphin.topology()

    assert len(nodes) == 75  # 150 objects over two pages, half are applications
    assert all(n.attributes["criticality"] == "High" for n in nodes)
    assert seen[0].headers["x-api-key"] == "key-123"
    assert seen[0].headers["tenant"] == "contoso"
    list_calls = [r for r in seen if r.url.path == "/v1/objects"]
    assert [r.url.params["skip"] for r in list_calls] == ["0", "100"]


async def test_bluedolphin_retries_once_on_rate_limit(monkeypatch):
    responses = iter([httpx.Response(429), httpx.Response(200, json={"items": []})])
    monkeypatch.setattr(bluedolphin, "MOCK", False)
    monkeypatch.setattr(bluedolphin, "_client", httpx.AsyncClient(
        base_url="https://x", transport=httpx.MockTransport(lambda r: next(responses))))
    monkeypatch.setattr(asyncio, "sleep", instant_sleep)
    assert await bluedolphin._get("/v1/objects") == {"items": []}
