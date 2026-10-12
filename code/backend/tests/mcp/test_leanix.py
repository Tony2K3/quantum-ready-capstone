import json

import httpx
import pytest

from connectors.sources import leanix, samples
from helpers import by_name, edge_between


# --- parsing ------------------------------------------------------------------

def test_leanix_sample_maps_fields():
    nodes, _ = leanix.to_topology(samples.leanix_fact_sheets())
    payroll = by_name(nodes, "Legacy Payroll")
    assert payroll.attributes["owner"] == "payroll@example.com"
    assert payroll.attributes["end_of_life"] == "2027-12-31"
    assert payroll.attributes["criticality"] == "businessCritical"
    assert payroll.attributes["hosting"] == "On-premises"
    assert payroll.attributes["business_unit"] == "Finance"
    assert by_name(nodes, "Payroll Run").attributes["sensitivity"] == "restricted"


def test_leanix_relations_become_edges():
    nodes, edges = leanix.to_topology(samples.leanix_fact_sheets())
    assert edge_between(edges, nodes, "HR Portal", "Identity Provider")[0].edge_type == "depends_on"
    assert edge_between(edges, nodes, "Identity Provider", "SSO Login (SAML)")[0].edge_type == "provides_interface"
    assert edge_between(edges, nodes, "IBM z/OS 2.4", "IBM")[0].edge_type == "supplied_by"


def test_leanix_relation_to_missing_fact_sheet_is_skipped():
    sheets = [{"id": "a", "name": "A", "type": "Application",
               "relToRequires": {"edges": [{"node": {"factSheet": {"id": "not-fetched"}}}]}}]
    _, edges = leanix.to_topology(sheets)
    assert edges == []


# --- live code paths against a fake API ----------------------------------------

async def test_leanix_live_auth_and_pagination(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "bearer-xyz", "expires_in": 3600})
        payload = json.loads(request.content)
        if 'keys: ["Application"]' not in payload["query"]:
            # other fact sheet types: return nothing
            return httpx.Response(200, json={"data": {"allFactSheets": {
                "pageInfo": {"hasNextPage": False, "endCursor": None}, "edges": []}}})
        second_page = payload["variables"]["cursor"] == "c1"
        node = {"id": "p2" if second_page else "p1", "name": "Page 2 App" if second_page else "Page 1 App",
                "type": "Application", "businessCriticality": "missionCritical"}
        return httpx.Response(200, json={"data": {"allFactSheets": {
            "pageInfo": {"hasNextPage": not second_page, "endCursor": None if second_page else "c1"},
            "edges": [{"node": node}]}}})

    monkeypatch.setattr(leanix, "MOCK", False)
    monkeypatch.setattr(leanix, "API_TOKEN", "token-abc")
    monkeypatch.setattr(leanix, "_client", httpx.AsyncClient(
        base_url="https://acme.leanix.net", transport=httpx.MockTransport(handler)))

    nodes, _ = await leanix.topology()

    assert sorted(n.name for n in nodes) == ["Page 1 App", "Page 2 App"]
    token_calls = [r for r in seen if r.url.path.endswith("/oauth2/token")]
    assert len(token_calls) == 1  # token reused across all queries
    graphql = [r for r in seen if r.url.path.endswith("/graphql")]
    assert all(r.headers["authorization"] == "Bearer bearer-xyz" for r in graphql)


async def test_leanix_graphql_error_is_raised(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "t"})
        return httpx.Response(200, json={"errors": [{"message": "Cannot query field 'dataClassification'"}]})

    monkeypatch.setattr(leanix, "MOCK", False)
    monkeypatch.setattr(leanix, "_client", httpx.AsyncClient(
        base_url="https://x", transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="dataClassification"):
        await leanix._pull_fact_sheets()
