# Chat Context Contract

---

## 1. Purpose

This document defines the contract between the roadmap generator
and the chat layer. It specifies:

- What data the roadmap generator produces and guarantees to be present
- How that data maps to the questions a user can ask in chat
- The MCP tool interface the roadmap generator will expose for the chat to call
- The evidence reference format used throughout the roadmap output

Update this document when making changes to the roadmap output format.

---

## 2. The Core Object: RoadmapOutput

Every chat session is associated with a `RoadmapOutput`. This is the
single object the chat layer works from. It is produced by the roadmap
generator and stored so the chat layer can retrieve it when it needs to.

```
RoadmapOutput
├── roadmap_id          uid for this roadmap run
├── persona             "EA", "CTO", "CISO"
├── generated_at        UTC timestamp
├── model               LLM model used (e.g. "claude-sonnet-4-5")
├── prompt_version      version of the system prompt used
├── assessment_version  version/ID of the assessment input (optional)
│
├── priorities          list[ApplicationPriority]  <- deterministic
├── summary             str                        <- LLM-generated
├── thirty_day_actions  list[RoadmapAction]        <- LLM-generated
├── sixty_day_actions   list[RoadmapAction]        <- LLM-generated
├── ninety_day_actions  list[RoadmapAction]        <- LLM-generated
├── long_term_roadmap   list[LongTermMilestone]    <- LLM-generated
├── assumptions         list[str]                  <- LLM-generated
└── missing_data        list[str]                  <- LLM-generated
```

Full schema: `src/roadmap/models/roadmap.py`

---

## 3. Sub-Object Schemas

### ApplicationPriority

Produced deterministically before the LLM is called. One per application. Describes the priority of an application for migration.

```
ApplicationPriority
├── application_id          str     e.g. "APP-001"
├── application_name        str     e.g. "Payment Service"
├── priority_level          str     "Critical", "High", "Medium", "Low"
├── priority_score          float   0-100, higher = more urgent
├── key_factors             list[str]   evidence references (see Section 5)
├── critical_check_failures list[str]   Jev dimension IDs that scored above 75% of their maximum scale
└── missing_fields          list[str]   fields absent at assessment time
```

### RoadmapAction

One recommended action within the 30/60/90 day plan.

```
RoadmapAction
├── id                  str     e.g. "ACTION-001"
├── application_id      str | None   None for org-wide actions
├── application_name    str | None
├── action              str     short imperative description
├── detail              str | None   longer explanation
├── reason              str     why this action is recommended now
├── priority            str     "Critical" | "High" | "Medium" | "Low"
├── timeframe           str     "30_days" | "60_days" | "90_days"
├── evidence            list[str]   evidence references (see Section 5)
├── depends_on          list[str]   action IDs that must be completed before this one
├── owner               str | None  owner of this action
└── assumptions         list[str]   assumptions behind this action
```

### LongTermMilestone

High-level strategic milestone in the 2-5 year horizon.

```
LongTermMilestone
├── year            str     "Year 1", "Years 2-3", "Years 4-5"
├── title           str
├── description     str
├── application_ids list[str]
├── goals           list[str]
├── dependencies    list[str]
└── assumptions     list[str]
```

Full schemas: `src/roadmap/models/roadmap.py`, `src/roadmap/models/priority.py`

---

## 4. Question-to-Field Mapping

This table shows which fields the chat layer should draw from to answer
each category of user question.

| User question | Primary field(s) |
|---|---|
| Why was this application prioritised? | `ApplicationPriority.key_factors`, `ApplicationPriority.priority_level` |
| What evidence supports this recommendation? | `RoadmapAction.evidence`, `ApplicationPriority.key_factors` |
| Why is this action in the 30-day plan? | `RoadmapAction.reason`, `ApplicationPriority.priority_score` |
| What applications depend on this one? | `EnterpriseArchitecture.connections` (see Section 6) |
| What happens if we delay this migration? | `RoadmapAction.depends_on`, `ApplicationPriority.critical_check_failures` |
| What assumptions did the roadmap make? | `RoadmapOutput.assumptions`, `RoadmapAction.assumptions` |
| What data is missing? | `RoadmapOutput.missing_data`, `ApplicationPriority.missing_fields` |
| What are the most urgent applications? | `RoadmapOutput.priorities` sorted by `priority_score` |
| What should we do in the next 30 days? | `RoadmapOutput.thirty_day_actions` |
| What is the long-term plan? | `RoadmapOutput.long_term_roadmap` |
| Why did this application get a critical rating? | `ApplicationPriority.critical_check_failures`, `ApplicationPriority.key_factors` |
| Who owns this action? | `RoadmapAction.owner` |
| What changed from the previous roadmap? | Compare `assessment_version` across two `RoadmapOutput` objects |

---

## 5. Evidence Reference Format

Every significant claim in the roadmap is backed by a reference to the
specific input data that supports it. Evidence strings use the format:

```
{application_id}.{field} = {value}
```

Examples:
```
APP-001.business_criticality = High
APP-001.data_longevity = Long
APP-001.NET-003 failed (severity=critical)
```

These appear in:
- `ApplicationPriority.key_factors`
- `RoadmapAction.evidence`

**Important:** The chat layer will use this information to find why a recommendation was made. No information should ever be invented. If so, there is an error.

---

## 6. Dependency Data

Application dependency information comes from `EnterpriseArchitecture`,
not from `RoadmapOutput` directly. The chat layer needs access to both.

The dependency graph answers questions like:
- "What applications does Payment Service depend on?"
- "What applications will be affected if we migrate Customer Portal?"

Connection schema:
```
Connection
├── source_application_id   str   the application that depends on the target
├── target_application_id   str   the application being depended upon
├── relationship            str   "API", "Database", "Message Queue", ...
├── dependency_type         str | None   "Required", "Optional"
└── criticality             str | None   "Low", "Medium", "High"
```

Direction: `source -> target` means source depends on / calls target.

Full schema: `src/roadmap/models/connection.py`

---

## 7. MCP Tool Interface

The roadmap generator will expose the following MCP tools for the chat layer to call.
These allow the chat system to retrieve specific data on demand rather
than loading the entire roadmap into every prompt.

**Not Implemented Yet**

### `get_roadmap(roadmap_id: str) -> RoadmapOutput`

Returns the full roadmap output for a given roadmap ID.
Use this when the user asks a broad question about the roadmap.

### `get_application_priority(roadmap_id: str, application_id: str) -> ApplicationPriority`

Returns the priority assessment for a single application.
Use this when the user asks why a specific application was prioritised
or what evidence backs its ranking.

### `get_actions_for_application(roadmap_id: str, application_id: str) -> list[RoadmapAction]`

Returns all actions across all timeframes that relate to a specific
application. Use this when the user asks what the plan is for a given app.

### `get_dependencies(application_id: str) -> dict`

Returns the connections involving a specific application:
```json
{
  "depends_on": ["Connection", "..."],
  "depended_on_by": ["Connection", "..."]
}
```
Use this when the user asks about upstream or downstream impact.

### `get_assessment_findings(application_id: str) -> list[Finding]`

Returns the Jev assessment scores for a specific application.
Use this when the user wants to understand the underlying quantum
exposure detail behind a priority or action.

---

## 8. Roadmap Versioning

Each `RoadmapOutput` has an `assessment_version` field that identifies
which assessment input it was generated from.

When an organisation reassesses and generates a new roadmap, the chat
layer can compare two `RoadmapOutput` objects by `assessment_version` to
answer questions like:
- "What changed from the last roadmap?"
- "Which applications improved?"
- "What new risks appeared?"

The roadmap generator does not implement comparison logic.

---

## 9. What Is Not in This Contract

The following are the chat layer's responsibility and are not defined here:

- How chat sessions are stored and retrieved
- How multi-session isolation is enforced
- The chat UI and conversation format
- How the chat LLM is prompted (separate from roadmap generation)
- How the MCP tools are registered with the MCP server
- Chat history persistence and export

---
