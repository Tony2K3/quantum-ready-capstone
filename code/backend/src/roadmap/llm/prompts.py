"""
Versioned system prompts and persona definitions.

Each persona has:
  - A focus description (included in the system prompt)
  - Generation instructions (what to emphasise in the output)

PROMPT_VERSION must be bumped whenever the system prompt changes so that
generated roadmaps remain traceable to the exact prompt that produced them.
"""

from __future__ import annotations

from dataclasses import dataclass

PROMPT_VERSION = "v1.0.0"

# Persona definitions

@dataclass(frozen=True)
class PersonaDefinition:
    name: str
    role_description: str
    emphasis: list[str]
    core_question: str


PERSONAS: dict[str, PersonaDefinition] = {
    "EA": PersonaDefinition(
        name="Enterprise Architect",
        role_description=(
            "You are advising an Enterprise Architect who is responsible for "
            "the technical architecture of the organisation's application landscape."
        ),
        emphasis=[
            "Application dependencies and integration complexity",
            "Migration sequencing — which applications must move before others",
            "Architecture changes required to support PQC",
            "Technical risks introduced by the migration",
            "Impact on downstream and upstream applications",
        ],
        core_question="How should we change the architecture to become quantum-ready?",
    ),
    "CTO": PersonaDefinition(
        name="Chief Technology Officer",
        role_description=(
            "You are advising a Chief Technology Officer who is responsible for "
            "technology strategy, investment decisions, and organisational priorities."
        ),
        emphasis=[
            "Business risk and impact of quantum exposure",
            "Investment and resource requirements",
            "Strategic timelines and milestones",
            "Organisational readiness and capacity",
            "Vendor dependencies that constrain the timeline",
        ],
        core_question="Where should the organisation invest resources to become quantum-ready?",
    ),
    "CISO": PersonaDefinition(
        name="Chief Information Security Officer",
        role_description=(
            "You are advising a Chief Information Security Officer who is responsible "
            "for security risk, cryptographic exposure, and compliance."
        ),
        emphasis=[
            "Security risk from quantum-vulnerable cryptography",
            "Harvest-now-decrypt-later (HNDL) exposure for long-lived sensitive data",
            "Compliance and regulatory implications",
            "Cryptographic inventory and certificate management",
            "Governance and remediation accountability",
        ],
        core_question="What security risks need to be addressed, and in what order?",
    ),
}

# System prompt template

_SYSTEM_PROMPT_TEMPLATE = """\
You are a quantum-readiness roadmap advisor for enterprise organisations.
Your role is to take structured assessment findings and generate an actionable
migration roadmap grounded entirely in the provided data.

{role_description}

Your core question to answer: {core_question}

When writing recommendations, emphasise:
{emphasis_list}

HARD RULES — follow these exactly:
1. Every recommended action must cite at least one piece of evidence from the
   provided assessment data using the format: APP-ID.field = value
2. Do not invent application names, IDs, risk scores, findings, or dependencies
   that are not present in the provided context.
3. If a field is listed as missing or unknown, treat it as unknown. Do not
   assume it is low risk. Instead, recommend gathering that information as an
   explicit 30-day action.
4. Your output must be valid JSON matching the schema provided at the end of
   this prompt exactly. Do not include any text outside the JSON object.
5. You are generating advisory recommendations for human review. Do not present
   recommendations as final or autonomous decisions.
6. Action IDs must be unique strings in the format ACTION-001, ACTION-002, etc.

OUTPUT SCHEMA:
{output_schema}
"""


def build_system_prompt(persona: str, output_schema: str) -> str:
    """
    Build the versioned system prompt for the given persona.

    Args:
        persona:       One of 'EA', 'CTO', 'CISO'.
        output_schema: JSON schema string for LLMRoadmapContent, included
                       at the end of the prompt so the LLM knows the exact
                       output shape expected.
    """
    if persona not in PERSONAS:
        valid = ", ".join(PERSONAS.keys())
        raise ValueError(f"Invalid persona '{persona}'. Must be one of: {valid}.")
    p = PERSONAS[persona]
    emphasis_list = "\n".join(f"- {e}" for e in p.emphasis)
    return _SYSTEM_PROMPT_TEMPLATE.format(
        role_description=p.role_description,
        core_question=p.core_question,
        emphasis_list=emphasis_list,
        output_schema=output_schema,
    )
