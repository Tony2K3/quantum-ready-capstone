# Data normalizer

Turns EA tool exports into the `EnterpriseArchitecture` the roadmap generator
consumes, and reports exactly what it did.

```
adapter (leanix.py / csv_native.py / bluedolphin.py)
    -> raw records (records.py)
    -> assemble.py: merge -> assign ids -> resolve references -> derive -> validate
    -> NormalizationResult(architecture, report)
```

Entry points: `normalize()` in `__init__.py` (Python callers, e.g. the
connector framework or an upload endpoint) and `python -m src.ingest` (local
use). Sources are applied in order; later sources override non-empty values.

## Rules

- **Nothing is guessed.** Risk and cryptography fields stay empty and are
  marked `missing` in `Application.field_sources` unless a source provides
  them. The only derived values are direct consequences of imported data:
  deployment environment from hosting type, lifecycle status from lifecycle
  dates, and an application's data objects from its interfaces. Each is
  labelled with how it was derived.
- **Direction:** an interface's consumer depends on its provider, so the
  connection goes consumer (source) -> provider (target).
- **Middleware** (IT components on an interface, e.g. Boomi) is kept in
  `Connection.via`, not added as graph nodes.
- **Unknown applications** referenced by name in an interface become
  `placeholder` applications. Interfaces missing a provider or consumer are
  reported and produce no connection.
- **Invalid values** are dropped field by field and reported with file, row
  and column; the rest of the record is kept.
- **Report messages** never include free-text cell contents such as
  descriptions, only the offending value.

## LeanIX

- Row 1 holds field keys; the label row and the `ReadMe` sheet are skipped.
- Supported types: `Application`, `Interface`, `ITComponent`. Other types are
  skipped and reported.
- Files are applied in order: unnumbered exports first, then numbered update
  files (`06_...`, `07_...`) ascending.
- Duplicates merge on LeanIX id, then `externalId`, then the `INT-###` code in
  the name, then the exact (normalized) name.
- Files named `*Template*` are skipped unless `--include-templates` is given:
  they contain example rows.
- Application ids are `APP-` plus a hash of the LeanIX id, or of the name
  when there is no LeanIX id (reported as `generated_id`).

| LeanIX column | Model field | Notes |
|---|---|---|
| `businessCriticality` | `business_criticality` | missionCritical/businessCritical -> High, businessOperational -> Medium, administrativeService -> Low; original kept in `extra_attributes` |
| `lxHostingType` | `hosting_type` (+ `deployment_environment`) | saas/paas/iaas -> Cloud, onPremise -> On-Premise, hybrid -> Hybrid, desktopOrLaptop -> On-Premise, mobile -> none |
| `lxTimeClassification` | `time_classification` | |
| `technicalSuitability` | `technical_fit` | |
| `subscriptions:RESPONSIBLE` | `owner` | |
| `relApplicationToOrganization` | `business_unit` | |
| `lifecycle:*` | `lifecycle_dates`, `lifecycle_status` | Excel serials or ISO dates |
| `relInterfaceToProviderApplication` / `...ConsumerApplication` | connection target / source | |
| `interfaceType` | `relationship` | synchronous -> API, asynchronous -> Message Queue, batch -> File Transfer, blank -> Other |
| `dataFlowDirection` | `direction` | falls back to `↔` / `→` in the name |
| `relInterfaceToITComponent` | `via` | |
| `relInterfaceToDataObject` | `data_objects` | |
| `relITComponentToApplication` (ITComponent) | `it_components` | |
| anything else | `extra_attributes` | |

## Native CSV

Blank templates are in `apps/decision-cortex/templates/` (or run
`python -m src.ingest template DIR`). Columns are model field names.

- Lists use `;` (e.g. `TLS 1.2;SSH 2`). Booleans accept `true/false/yes/no`.
- Lifecycle dates: `lifecycle_plan`, `lifecycle_phase_in`, `lifecycle_active`,
  `lifecycle_phase_out`, `lifecycle_end_of_life` (YYYY-MM-DD).
- Connections reference applications by id, or by name as a fallback. Unknown
  references are errors (no placeholders).
- To add crypto/risk data to a LeanIX import: run the LeanIX import, copy the
  application ids from `architecture.json` into `applications.csv`, fill in
  the columns, then import with `--overlay-csv`.

Allowed values are the `Literal` types in `src/roadmap/models/application.py`
and `connection.py`; invalid values are reported with the allowed list.

## BlueDolphin

Not implemented yet: The intended mapping is in `bluedolphin.py`.
