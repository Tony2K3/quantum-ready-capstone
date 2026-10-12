# Roadmap Generator (Decision Cortex)

Generates persona-specific (EA, CTO, CISO) post-quantum migration roadmaps from
an enterprise architecture assessment.

## Pipeline

1. **Input contracts** (`models/`) – Pydantic models for the enterprise
   architecture (applications + connections), priority scores, and roadmap output.
2. **Quantum priority scoring** (`analysis/jev_scoring.py`) – each application is
   scored concurrently by TypeSafe AI's Jev model across five independent
   dimensions and mapped to ranked `PriorityScore` objects.
3. **Prompt assembly** (`llm/prompts.py`, `llm/context.py`) – builds a
   persona-specific prompt from the scored architecture.
4. **Roadmap generation** (`llm/caller.py`) – calls Anthropic Claude for a
   structured 30/60/90-day and 2–5 year roadmap, validated against the
   `RoadmapOutput` schema with retry on failure.

`pipeline.py` exposes the whole flow as a single `generate_roadmap(...)` function.

## Docs

- [`docs/prompt_strategy.md`](docs/prompt_strategy.md) – prompt design and the
  split between deterministic and LLM responsibilities.
- [`docs/chat_context_contract.md`](docs/chat_context_contract.md) – chat context
  contract and MCP tool interface for downstream integration.

## Environment setup

Create a `.env` file in `code/backend/` (ignored by git):

```
JEV_N8N_URL=https://your-n8n-instance/webhook/jev
ANTHROPIC_API_KEY=sk-...
```

## Running tests

From `code/backend/`:

```bash
pip install -r src/roadmap/requirements.txt
pytest tests/roadmap -v
```
