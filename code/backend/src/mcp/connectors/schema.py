"""qros topology schema — the shape every source maps into. Confirm exact
field names against Peter's roadmap generator input."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

NODE_TYPES = ("application", "data_object", "interface", "it_component", "business_capability", "provider")

# Standard attribute keys. Every node carries the keys that apply to it;
# unknown source fields go into "other_properties".
ATTR_KEYS = (
    "description", "owner", "status", "lifecycle", "end_of_life", "criticality",
    "hosting", "vendor", "sensitivity", "category", "workspace", "business_unit",
    "retention", "protocols", "network_exposure", "migration_complexity",
    # crypto fields: only filled when INCLUDE_CRYPTO_FIELDS is True
    "cryptography", "pqc_readiness", "crypto_agility", "key_management_type",
)

# Peter's Application schema for the roadmap generator, in his field order.
APPLICATION_FIELDS = (
    "id", "name", "description", "business_unit", "owner", "business_criticality",
    "data_sensitivity", "data_longevity", "vendor_dependency", "tech_stack",
    "deployment_environment", "migration_complexity", "cryptography", "pqc_readiness",
    "network_protocols", "network_exposure", "crypto_agility", "key_management_type",
)


@dataclass(frozen=True)
class Node:
    id: str               # prefixed by source: "bd:..." or "lx:..."
    source: str           # "bluedolphin" | "leanix"
    node_type: str        # one of NODE_TYPES
    name: str
    attributes: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    id: str
    source: str
    edge_type: str        # depends_on, uses_data, runs_on, supports, ...
    from_node_id: str
    to_node_id: str
    label: str = ""       # the source's own name for the relationship


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DOWN = "down"


@dataclass(frozen=True)
class HealthStatus:
    source: str
    state: HealthState
    detail: str | None = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
