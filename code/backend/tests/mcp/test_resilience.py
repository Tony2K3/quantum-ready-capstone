import httpx

from connectors import tools, topology
from connectors.resilience import CircuitBreaker, call_resilient
from connectors.sources import leanix


async def test_one_source_down_still_returns_the_other(monkeypatch):
    async def broken():
        raise httpx.ConnectError("LeanIX unreachable")

    monkeypatch.setattr(leanix, "topology", broken)
    monkeypatch.setattr(topology, "call_resilient", _no_backoff(call_resilient))

    result = await tools.fetch_nodes()
    assert result["is_partial"] is True
    assert result["sources_ok"] == ["bluedolphin"]
    assert "leanix" in result["sources_failed"]
    assert result["count"] > 0
    assert all(n["source"] == "bluedolphin" for n in result["nodes"])


async def test_circuit_breaker_opens_and_skips_calls():
    calls = 0

    async def always_fails():
        nonlocal calls
        calls += 1
        raise RuntimeError("down")

    breaker = CircuitBreaker(failure_threshold=1, reset_after_seconds=999)
    _, err1 = await call_resilient(always_fails, source="t", breaker=breaker, max_retries=0)
    _, err2 = await call_resilient(always_fails, source="t", breaker=breaker, max_retries=0)
    assert "down" in err1
    assert "circuit open" in err2
    assert calls == 1


def _no_backoff(fn):
    async def wrapper(*args, **kwargs):
        kwargs["backoff_seconds"] = 0
        return await fn(*args, **kwargs)
    return wrapper
