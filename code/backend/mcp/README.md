# Decision Cortex — MCP connector server

Pulls enterprise-architecture data from **BlueDolphin** and **LeanIX**, maps both
into one shared node/edge shape (the qros topology schema Peter's roadmap
generator expects), and exposes it through MCP tools.

Each source is wrapped with a timeout, retries and a circuit breaker, so one going
down never blocks the other's data. With no credentials set, each source falls
back to built-in sample data, so the server works offline for demos.

## Quick start

Requires Python 3.10+.

Run from this folder (`code/backend/mcp`):

```sh
python ../src/mcp/server.py   # starts the MCP server over stdio
python -m pytest              # runs the unit tests (no network needed)
```

`server.py` installs `requirements.txt` on its own if `mcp` or `httpx` is missing,
into the Python that runs it. To run the tests before ever starting the server,
run `pip install -r requirements.txt` first.

> `mcp` is pinned below 2.0 because mcp 2.x renamed `FastMCP` to `MCPServer`.
 
## Folder layout

```
code/backend/
├── mcp/                          docs and config (this folder)
│   ├── README.md
│   ├── requirements.txt
│   ├── pytest.ini                points pytest at src/mcp and tests/mcp
│   └── example_output/           what export_csv writes using the sample data
├── src/mcp/                      the code
│   ├── server.py                 entry point: python ../src/mcp/server.py
│   └── connectors/
│       ├── config.py             switches: INCLUDE_CRYPTO_FIELDS, CACHE_SECONDS
│       ├── schema.py             Node, Edge, HealthStatus, standard field lists
│       ├── normalize.py          raw source fields -> standard attributes; edge rules
│       ├── resilience.py         CircuitBreaker + call_resilient (timeout/retry)
│       ├── sources/
│       │   ├── bluedolphin.py    BlueDolphin REST client + parser
│       │   ├── leanix.py         LeanIX GraphQL client + parser
│       │   └── samples.py        offline sample data for both sources
│       ├── topology.py           pulls both sources in parallel and merges them
│       ├── applications.py       builds Peter's Application records
│       ├── export.py             CSV tables + writer
│       └── tools.py              the MCP tools
└── tests/mcp/                    one test file per module (conftest.py resets state)
```

How data flows through it:

```
sources/bluedolphin.py ─┐                        ┌─> applications.py ─┐
                        ├─> topology.py (merge) ─┤                    ├─> tools.py (MCP)
sources/leanix.py ──────┘                        └─> export.py ───────┘
        (both use normalize.py + resilience.py)
```

## MCP tools

| Tool | What it returns |
|---|---|
| `fetch_applications()` | Applications in Peter's schema (see below) |
| `fetch_nodes(node_type=None)` | Nodes from both sources, optionally one type |
| `fetch_edges(edge_type=None)` | Edges from both sources, optionally one type |
| `health_check()` | Whether each source is answering |
| `export_csv(output_dir="export")` | Writes one CSV per entity type |

Every tool except `health_check` also returns `sources_ok`, `sources_failed`,
`is_partial` and `mode` (`sample` or `live` per source), so a caller can tell when
one source's data is missing.

## What gets pulled

**Nodes**

| Type | Main fields |
|---|---|
| `application` | owner, status, lifecycle, end of life, business criticality, hosting, vendor |
| `data_object` | data classification / sensitivity, owner, retention |
| `interface` | data flows between applications, protocols |
| `it_component` | tech stack under apps (OS, databases, middleware, platforms), lifecycle, end of life, vendor |
| `business_capability` | what the business does, for exec-level grouping |
| `provider` | vendors / suppliers |

**Edges**

| Type | Meaning |
|---|---|
| `depends_on` | app → app it needs (drives migration order) |
| `uses_data` | app → data object |
| `runs_on` | app → IT component |
| `supports` | app → business capability |
| `provides_interface` / `consumes_interface` / `connects_interface` | app → interface |
| `carries_data` | interface → data object |
| `supplied_by` | app or IT component → provider |

Source fields that don't match a standard attribute land in `other_properties`.

## Application output (Peter's schema)

`fetch_applications` and `applications.csv` use the roadmap generator's Application
fields, in this order:

```
id, name, description, business_unit, owner, business_criticality,
data_sensitivity, data_longevity, vendor_dependency, tech_stack,
deployment_environment, migration_complexity, cryptography,
pqc_readiness, network_protocols, network_exposure, crypto_agility,
key_management_type
```

When an app doesn't record a field itself, the field is filled from what the app is connected to:

| Field | Derived from |
|---|---|
| `data_sensitivity` | most sensitive data object the app uses |
| `data_longevity` | retention of the data objects the app uses |
| `vendor_dependency` | app vendor + its providers + vendors of its tech stack |
| `tech_stack` | IT components the app runs on |
| `network_protocols` | app's own protocols + those of its interfaces |

`migration_complexity` isn't a standard field in either tool, so it's only filled
if the customer has a custom field for it. `applications.csv` adds extra context
columns after Peter's fields (source, lifecycle, depends_on, needed_by, …).

### Crypto fields are off for now

Encryption and crypto fields (algorithms, key lengths, certificates, PQC readiness)
are dropped on purpose until the team decides how to handle them. Peter's schema
keeps those columns, but they stay empty. To include them, set
`INCLUDE_CRYPTO_FIELDS = True` in `src/mcp/connectors/config.py`.

## CSV export

`export_csv` writes these files. `example_output/` shows them built from the
sample data.

| File | Contents |
|---|---|
| `applications.csv` | Peter's schema + context columns |
| `dependencies.csv` | every `depends_on` edge |
| `data_objects.csv` | data objects, which apps use them, which interfaces carry them |
| `interfaces.csv` | interfaces, provider/consumer apps, data carried |
| `it_components.csv` | tech stack, lifecycle, end of life, which apps run on it |
| `business_capabilities.csv` | capabilities and the apps supporting them |
| `relationships.csv` | every edge of every type |

## Connecting real data

Set environment variables before starting the server. You don't need to change
any code. Each source switches from sample data to live data on its own, as soon
as its variables are set.

**BlueDolphin**

| Variable | Value |
|---|---|
| `BLUEDOLPHIN_API_KEY` | your user API key (BlueDolphin → user settings) |
| `BLUEDOLPHIN_TENANT` | your tenant name |
| `BLUEDOLPHIN_REGION` | `eu` (default) or `us` |

**LeanIX**

| Variable | Value |
|---|---|
| `LEANIX_API_TOKEN` | API token (LeanIX admin → technical users) |
| `LEANIX_HOST` | your LeanIX host, e.g. `acme.leanix.net` |

### Things to check on the first live run

- **BlueDolphin object type names differ per tenant.** If a type comes back
  empty, add the tenant's name for it to `TYPE_MAP` in
  `connectors/sources/bluedolphin.py`.
- **Custom property names differ per tenant too** (e.g. "Business Criticality"
  vs "Criticality"). Add missing names to `FIELD_ALIASES` in
  `connectors/normalize.py`. Anything not matched still lands in
  `other_properties`.
- **BlueDolphin's `related_objects` layout isn't documented publicly.**
  `_relation_parts()` in `bluedolphin.py` handles the likely shapes. If
  `dependencies.csv` is empty but BlueDolphin shows relationships, that function
  needs adjusting.
- **LeanIX field names can vary with the workspace's meta model.** A GraphQL
  error naming a field means that field needs removing or renaming in
  `TYPE_FIELDS` in `connectors/sources/leanix.py`.

## Tests

From this folder:

```sh
python -m pytest -v
```

The tests need no credentials or network access. The "live" tests point the real
HTTP code at fake BlueDolphin and LeanIX APIs (`httpx.MockTransport`), so they check
the request and parsing logic without calling the real services.
