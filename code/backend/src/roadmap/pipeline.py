"""
Decision Cortex pipeline top-level entry point.

This is the only file an external caller needs to import from.
The internals (quantum scoring, context assembly, LLM calling) are
hidden behind a single function.

Usage:
    from src.roadmap.pipeline import generate_roadmap
    from src.roadmap.models import EnterpriseArchitecture, Application

    architecture = EnterpriseArchitecture(applications=[...], connections=[...])

    output = generate_roadmap(
        architecture=architecture,
        persona="CISO",
        api_key="sk-...",
        organization="Acme Corp",
    )
"""

from __future__ import annotations

from .analysis.jev_scoring import JevClient, score_applications
from .llm.caller import DEFAULT_MODEL, RoadmapCaller
from .llm.context import assemble_prompt
from .models.enterprise_architecture import EnterpriseArchitecture
from .models.roadmap import RoadmapOutput


def generate_roadmap(
    architecture: EnterpriseArchitecture,
    persona: str,
    api_key: str,
    jev_client: JevClient | None = None,
    organization: str = "the organisation",
    model: str = DEFAULT_MODEL,
    workspace_id: str | None = None,
    assessment_version: str | None = None,
) -> RoadmapOutput | None:
    """
    Run the full Decision Cortex pipeline and return a structured roadmap.

    Args:
        architecture:       Validated enterprise architecture (applications +
                            connections). Build from connector data or CSV.
        persona:            One of 'EA', 'CTO', 'CISO'.
        api_key:            Anthropic API key for the LLM call.
        jev_client:         JevClient instance. Defaults to JevClient.from_n8n().
        organization:       Human-readable organisation name.
        model:              LLM model identifier. Defaults to claude-sonnet-4-5.
        assessment_version: Optional identifier for the assessment input.

    Returns:
        RoadmapOutput — the complete structured roadmap including priorities,
        30/60/90 day actions, long-term milestones, and provenance metadata.

    Pipeline steps:
        1. Jev scoring      — scores each application across five dimensions
        2. Context assembly — builds the LLM prompt
        3. LLM call         — Claude generates roadmap content
        4. Output assembly  — combines priorities + LLM content + metadata
    """
    if jev_client is None:
        jev_client = JevClient.from_n8n()

    # 1. Jev scoring
    priorities = score_applications(architecture, jev_client)

    # --- TEMPORARY: consistency check — run scoring twice and compare ---
    priorities_run2 = score_applications(architecture, jev_client)

    def _print_priorities(label: str, ps: list) -> None:
        print(f"\n--- {label} ---")
        for p in ps:
            print(f"  {p.application_name} ({p.application_id}) — {p.priority_level} ({p.priority_score:.1f})")
            for kf in p.key_factors:
                print(f"    - {kf}")
            if p.missing_fields:
                print(f"    missing: {', '.join(p.missing_fields)}")
        print(f"--- end {label} ---")

    _print_priorities("Run 1", priorities)
    _print_priorities("Run 2", priorities_run2)

    print("\n--- Jev consistency check ---")
    for p1, p2 in zip(
        sorted(priorities, key=lambda p: p.application_id),
        sorted(priorities_run2, key=lambda p: p.application_id),
    ):
        score_delta = abs(p1.priority_score - p2.priority_score)
        level_match = p1.priority_level == p2.priority_level
        print(
            f"  {p1.application_name:<25} "
            f"run1={p1.priority_score:.1f} ({p1.priority_level:<8})  "
            f"run2={p2.priority_score:.1f} ({p2.priority_level:<8})  "
            f"delta={score_delta:.1f}  level_match={level_match}"
        )
    print("--- end consistency check ---\n")
    # --- END TEMPORARY ---

    # 2. Context assembly
    prompt_payload = assemble_prompt(
        priorities=priorities,
        architecture=architecture,
        persona=persona,
        organization=organization,
    )

    # 3 + 4. LLM call and output assembly
    if not api_key:
        print("No API key provided — skipping LLM call.")
        return None

    caller = RoadmapCaller(api_key=api_key, model=model, workspace_id=workspace_id)
    return caller.generate(
        payload=prompt_payload,
        priorities=priorities,
        persona=persona,
        assessment_version=assessment_version,
    )
