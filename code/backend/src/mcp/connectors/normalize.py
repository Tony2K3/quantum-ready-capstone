"""Mapping helpers shared by every source: raw fields -> standard attribute
keys, and node pairs -> canonical edges."""

from __future__ import annotations

import json

from . import config
from .schema import ATTR_KEYS, Edge, Node

_CRYPTO_WORDS = ("encrypt", "crypto", "cipher", "algorithm", "key length", "key management",
                 "kms", "certificate", "pqc", "quantum")

# Source field names (lower-case) that map onto each standard attribute.
# Tenants name custom properties differently; add missing names here.
FIELD_ALIASES = {
    "owner": ["owner", "application owner", "business owner", "technical owner", "responsible"],
    "lifecycle": ["lifecycle", "lifecycle status", "lifecycle phase", "life cycle", "lifecycle stage"],
    "end_of_life": ["end of life", "end-of-life", "eol", "end date", "retirement date",
                    "decommission date", "sunset date"],
    "criticality": ["business criticality", "criticality", "business critical"],
    "hosting": ["hosting", "hosting type", "deployment", "deployment model", "hosting model"],
    "vendor": ["vendor", "supplier", "provider", "manufacturer"],
    "sensitivity": ["data classification", "classification", "sensitivity", "confidentiality",
                    "information classification"],
    "category": ["category", "technology type", "component type", "technology category"],
    "description": ["description"],
    "business_unit": ["business unit", "department", "division", "organization", "organisation",
                      "user group"],
    "retention": ["data longevity", "data retention", "retention", "retention period",
                  "retention time"],
    "protocols": ["protocol", "protocols", "network protocol", "network protocols",
                  "interface technology", "communication protocol"],
    "network_exposure": ["network exposure", "exposure", "internet facing", "internet-facing",
                         "network zone"],
    "migration_complexity": ["migration complexity", "complexity"],
    "cryptography": ["cryptography", "encryption", "crypto"],
    "pqc_readiness": ["pqc readiness", "quantum readiness", "pqc status"],
    "crypto_agility": ["crypto agility", "crypto-agility", "cryptographic agility"],
    "key_management_type": ["key management", "key management type", "kms"],
}

# Canonical edge type for a (from_type, to_type) pair.
EDGE_RULES = {
    ("application", "application"): "depends_on",
    ("application", "data_object"): "uses_data",
    ("application", "it_component"): "runs_on",
    ("application", "business_capability"): "supports",
    ("application", "interface"): "connects_interface",
    ("interface", "data_object"): "carries_data",
    ("application", "provider"): "supplied_by",
    ("it_component", "provider"): "supplied_by",
    ("it_component", "it_component"): "depends_on",
}


def text(value) -> str:
    """Flatten nested API values to plain text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("name", "title", "object_title", "date", "value", "email"):
            if value.get(key) not in (None, ""):
                return str(value[key])
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "; ".join(t for t in (text(v) for v in value) if t)
    return str(value)


def _is_crypto_field(name: str) -> bool:
    n = name.lower()
    return any(w in n for w in _CRYPTO_WORDS)


def normalize_attributes(raw: dict) -> dict:
    """Map raw source fields onto the standard attribute keys. Whatever
    doesn't match goes into other_properties (crypto fields dropped unless
    INCLUDE_CRYPTO_FIELDS is on)."""
    attrs = {k: "" for k in ATTR_KEYS}
    other = {}
    for key, value in raw.items():
        if not config.INCLUDE_CRYPTO_FIELDS and _is_crypto_field(key):
            continue
        value_text = text(value)
        k = key.strip().lower()
        for std, aliases in FIELD_ALIASES.items():
            if k in aliases:
                if not attrs[std]:
                    attrs[std] = value_text
                break
        else:
            if value_text:
                other[key] = value_text
    attrs["other_properties"] = other
    return attrs


def make_edge(source: str, a: Node, b: Node, label: str = "", edge_type: str | None = None) -> Edge:
    """Build an edge in canonical direction. If edge_type isn't given, it's
    inferred from the node types (flipping direction if needed)."""
    if edge_type is None:
        pair = (a.node_type, b.node_type)
        if pair in EDGE_RULES:
            edge_type = EDGE_RULES[pair]
        elif (pair[1], pair[0]) in EDGE_RULES:
            a, b = b, a
            edge_type = EDGE_RULES[(a.node_type, b.node_type)]
        else:
            edge_type = "related_to"
    return Edge(
        id=f"{a.id}->{b.id}:{edge_type}", source=source, edge_type=edge_type,
        from_node_id=a.id, to_node_id=b.id, label=label,
    )
