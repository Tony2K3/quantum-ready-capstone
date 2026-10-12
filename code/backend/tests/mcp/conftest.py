"""Shared test setup.

No credentials or network needed. The "live" tests point the real HTTP
code at fake BlueDolphin / LeanIX APIs (httpx.MockTransport), so they check
the request/parsing logic without touching the real services.
"""

import pytest

from connectors import config
from connectors.resilience import CircuitBreaker
from connectors.sources import bluedolphin, leanix


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    """Every test starts on sample data with empty caches and closed breakers."""
    monkeypatch.setattr(bluedolphin, "MOCK", True)
    monkeypatch.setattr(leanix, "MOCK", True)
    monkeypatch.setattr(config, "INCLUDE_CRYPTO_FIELDS", False)
    monkeypatch.setattr(bluedolphin, "_cache", None)
    monkeypatch.setattr(leanix, "_cache", None)
    monkeypatch.setattr(leanix, "_token", None)
    monkeypatch.setattr(bluedolphin, "breaker", CircuitBreaker())
    monkeypatch.setattr(leanix, "breaker", CircuitBreaker())
    monkeypatch.setattr(bluedolphin, "_MIN_INTERVAL", 0)
