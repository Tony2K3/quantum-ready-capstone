# LLM Prompt Strategy — Decision Cortex Roadmap Generator

## 1. The LLM's Job

The LLM is responsible for reasoning and explanation, not for data analysis.

All factual inputs (quantum vulnerability, risk scores, application data, dependency
relationships) arrive pre-computed from deterministic systems. The LLM's job is to
take those structured findings and answer:

> *"Given everything we know about this organisation's applications, what should
> they do, in what order, and why?"*

LLM outputs:
- Reason about prioritisation and sequencing across the application portfolio
- Generate 30 / 60 / 90 day actions grounded in the findings
- Generate a 2–5 year strategic roadmap
- Explain recommendations in plain language
- Adapt explanation and emphasis to the selected persona
- Highlight missing data and assumptions explicitly

---

## 2. Deterministic vs. LLM Responsibilities

```
Connector / CSV
      ↓
Validation + Normalisation     ← deterministic
      ↓
Dependency Graph               ← deterministic
      ↓
Jev Scoring                    ← deterministic (TypeSafe AI)
      ↓
LLM Context Assembly           ← deterministic
      ↓
LLM Reasoning                  ← LLM
      ↓
Structured Output Validation   ← deterministic (Pydantic schema)
```

Priority scoring, risk values, and vulnerability findings are fixed before the LLM
is called. The LLM receives a summary of what is already known — it does not re-derive it.

---

## 3. Prompt Structure

Each roadmap generation call uses a three-part prompt:

```
[ System Prompt ]
  Role, persona, hard constraints, output format instructions

[ Context Block ]
  Structured summary of the analysed enterprise architecture:
    - Application summaries in priority order
    - Key factors and evidence per application
    - Dependency graph summary
    - Missing data gaps

[ Generation Instructions ]
  Specific task for this call:
    - Generate 30/60/90 day actions
    - Generate long-term roadmap
    - Focus on persona-relevant concerns
```

These three parts are assembled programmatically by `src/roadmap/llm/context.py`

---

## 4. System Prompt

The system prompt establishes the LLM's role and hard constraints. It is versioned
(`PROMPT_VERSION` in `src/llm/prompts.py`) and must be bumped whenever it changes
so that generated roadmaps remain traceable to the exact prompt that produced them.

Hard rules enforced in the system prompt:

1. Every recommended action must cite at least one piece of evidence from the
   provided assessment data.
2. Do not invent application names, IDs, risk scores, or findings not present
   in the context.
3. If a field is missing or unknown, treat it as unknown. Doesnt assume low risk.
4. Output must be valid JSON matching the `LLMRoadmapContent` schema exactly.
5. Recommendations are advisory. Do not present them as final decisions.
6. Action IDs must be unique strings in the format `ACTION-001`, `ACTION-002`, etc.

---

## 5. Context Block

The context block is built deterministically in `src/llm/context.py` before calling
the LLM. It is plain text rather than raw JSON to keep it token-efficient and
readable in logs.

Structure:

```
ASSESSMENT CONTEXT
==================
Organisation: {org_name}
Applications assessed: {count}
Critical: {n}  |  High: {n}  |  Medium: {n}  |  Low: {n}

APPLICATIONS (highest priority first)
--------------------------------------
[1] Payment Service (APP-001) — CRITICAL
    Priority score: 85.0
    Key factors: APP-001.business_criticality = High, APP-001.data_longevity = Long
    Critical check failures: NET-003
    Missing data: APP-001.crypto_agility, APP-001.network_protocols

[2] ...

KEY DEPENDENCIES
----------------
- APP-001 → APP-003 (API, Required)

MISSING DATA
------------
- APP-001.crypto_agility
- APP-002.owner
```

---

## 6. Persona Layer

The persona changes what is emphasised and how recommendations are explained.

All three personas operate from the same findings. The persona layer is
applied in `src/llm/prompts.py` at two points:

1. The system prompt receives the persona role description and emphasis list.
2. The generation instructions include a persona-specific framing note.

### Enterprise Architect (EA)

Core question: *"How should we change the architecture?"*

Emphasis: application dependencies, integration complexity, migration sequencing,
architecture changes required, technical risks.

### Chief Technology Officer (CTO)

Core question: *"Where should the organisation invest resources?"*

Emphasis: business risk, investment required, resource implications, strategic
timelines, organisational impact.

### Chief Information Security Officer (CISO)

Core question: *"What security risks need to be addressed?"*

Emphasis: security exposure, cryptographic risk, sensitive data handling, compliance
implications, governance requirements.

---

## 7. Evidence and Grounding

Every significant recommendation must cite the specific assessment data that
supports it. Evidence strings use the format:

```
{application_id}.{field} = {value}
```

Examples:
```
APP-001.business_criticality = High
APP-001.data_longevity = Long
APP-001.NET-003 failed (severity=critical)
```

The LLM is instructed to populate the `evidence` field on each action with
references drawn from the `key_factors` in the context block.

The LLM is explicitly told not to include evidence it cannot find in the provided
context. This is enforced as a hard rule in the system prompt and validated by
checking that every action has at least one evidence entry.

---

## 8. Handling Missing Data

Missing data must be surfaced, not silently filled in.

If a field is `None` or unknown, the LLM should:
- Acknowledge the gap in the `assumptions` field of the output
- Generate a 30-day action to gather the missing information
- Never assume the missing value is `Low` or non-problematic

The generation instructions explicitly state:
> "For every missing data field listed above, include a 30-day action to gather
> that information. Do not assume a value for missing fields."

---

## 9. Structured Output

The LLM is asked to return JSON matching the `LLMRoadmapContent` schema defined
in `src/models/roadmap.py`.

To get structured output reliably:
- The full JSON schema is appended to the system prompt
- The LLM is told: *"Your entire response must be a single valid JSON object
  matching this schema exactly. No text before or after the JSON."*
- The output is parsed and validated with Pydantic immediately after the LLM call
  in `src/roadmap/llm/caller.py`
- If validation fails, the call is retried once before raising `LLMValidationError`

---

## 10. Reliability Controls

| Control | Approach |
|---|---|
| Structured output | JSON schema appended to system prompt; JSON mode where provider supports it |
| Schema validation | Pydantic validates every LLM response before it is returned |
| Prompt versioning | `PROMPT_VERSION` in `src/roadmap/llm/prompts.py` — bump on any system prompt change |
| Model versioning | Model name recorded in `RoadmapOutput.model` |
| Evidence requirements | LLM instructed to cite evidence; enforced as a hard rule |
| "Do not invent" instruction | Explicit in system prompt |
| Retry on invalid output | One retry on schema validation failure, then raise `LLMValidationError` |

---
