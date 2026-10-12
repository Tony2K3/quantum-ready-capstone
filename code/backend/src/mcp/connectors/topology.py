"""Pulls both sources in parallel and merges them into one node/edge list.
A source that fails is reported in sources_failed instead of raising."""

from __future__ import annotations

import asyncio

from .resilience import call_resilient
from .sources import bluedolphin, leanix

# Keys of all_topology()'s result that every tool passes through to its caller.
STATUS_KEYS = ("sources_ok", "sources_failed", "is_partial", "mode")


async def all_topology() -> dict:
    (bd, bd_err), (lx, lx_err) = await asyncio.gather(
        call_resilient(bluedolphin.topology, source="bluedolphin", breaker=bluedolphin.breaker, default=([], [])),
        call_resilient(leanix.topology, source="leanix", breaker=leanix.breaker, default=([], [])),
    )
    errors = {s: e for s, e in (("bluedolphin", bd_err), ("leanix", lx_err)) if e}
    return {
        "nodes": [*bd[0], *lx[0]],
        "edges": [*bd[1], *lx[1]],
        "sources_ok": [s for s in ("bluedolphin", "leanix") if s not in errors],
        "sources_failed": errors,
        "is_partial": bool(errors),
        "mode": {
            "bluedolphin": "sample" if bluedolphin.MOCK else "live",
            "leanix": "sample" if leanix.MOCK else "live",
        },
    }


def status(topo: dict) -> dict:
    """The source-status part of an all_topology() result."""
    return {k: topo[k] for k in STATUS_KEYS}
