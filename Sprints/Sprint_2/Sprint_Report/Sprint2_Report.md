# Sprint 2 Report – Quantum Ready

**Project:** Quantum Ready  
**Team Members:** Tony Cao, Peter Liu, Russell Habib  
**Sprint Period:** 010/05/2026 – 11/05/2026

## YouTube Link of Sprint 2 Video

[Sprint 2 Demo]()

## What's New (User Facing)

**Tony – Simulation, Decisioning & Quality (M1)**
- Implemented the core simulation engine to compare current and proposed infrastructure readiness.
- Added scenario-based simulation, currently supporting pqc-hardening.
- Developed API endpoints to execute simulations and retrieve available scenarios.
- Integrated the Python simulation API with the Fastify backend.
- Enabled comparison of readiness scores, failing findings, and affected infrastructure nodes.

**Peter – AI Reasoning & Roadmap Intelligence**

**Russell – Connector & Integration**

## Work Summary (Developer Facing)

**Tony:**

During Sprint 2, I implemented the core Simulation Engine using the existing QROS scoring system. The engine applies proposed infrastructure changes to a copy of the original topology and compares readiness assessments before and after simulation. I also implemented scenario handling and topology dependency analysis. Additionally, I developed a FastAPI service and connected it to the Fastify backend through GET and POST endpoints. Both endpoints were successfully tested locally using sample topology data.

**Peter:**


**Russell:**


## Unfinished Work

**Tony:**
- No unfinished work identified within the assigned M2 requirements and architecture scope.

**Peter:**
- All Sprint 1 responsibilities were completed.

**Russell:**

NA

## Completed Issues/User Stories

**Tony:**
- Defined in Clickup

**Peter:**
- Defined in Clickup

**Russell:**
- Defined in Clickup

## Incomplete Issues/User Stories

**Tony:**
- Frontend integration and deployment are pending.


## Code Files for Review

**Tony – Simulator Architecture**
- [engine.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/engine.py) – Core simulation workflow and assessment comparison design.
- [relationships.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/relationships.py) – Topology relationship and dependency handling.
- [README.md](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/README.md) – Simulator requirements and architecture documentation.
- [demo.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/demo.py) – Demonstrates the simulation workflow using sample topology data.
- [test_engine.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/simulator/test_engine.py) – Validates simulation behavior, topology preservation, and assessment results.
- [test_relationships.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/simulator/test_relationships.py) – Validates topology relationship handling and dependency identification.
- [simulation.ts](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/simulation.ts) - Fastify routes forwarding requests to the Python service.
- [index.ts](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/index.ts) - Registers simulation routes in the Fastify backend.
- [api.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/api.py) - FastAPI endpoints for simulation requests.

**Peter – Roadmap Generator (Decision Cortex)**
- [pipeline.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/roadmap/pipeline.py) – End-to-end entry point from enterprise architecture input to validated roadmap output.
- [jev_scoring.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/roadmap/analysis/jev_scoring.py) – Concurrent per-application quantum priority scoring with TypeSafe AI's Jev model.
- [prompts.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/roadmap/llm/prompts.py) – Persona definitions (EA, CTO, CISO) and versioned prompt templates.
- [context.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/roadmap/llm/context.py) – Assembles scored assessment data into the persona-specific prompt.
- [caller.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/roadmap/llm/caller.py) – Anthropic Claude roadmap generation with schema validation and retry logic.
- [models/](https://github.com/Tony2K3/quantum-ready-capstone/tree/main/code/backend/src/roadmap/models) – Pydantic data contracts for enterprise architecture, priority scores, and roadmap output.
- [prompt_strategy.md](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/roadmap/docs/prompt_strategy.md) – Prompt strategy and deterministic vs. LLM responsibilities.
- [chat_context_contract.md](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/roadmap/docs/chat_context_contract.md) – Chat context contract and MCP tool interface for downstream integration.
- [README.md](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/roadmap/README.md) – Roadmap generator overview, setup, and test instructions.
- [tests/roadmap/](https://github.com/Tony2K3/quantum-ready-capstone/tree/main/code/backend/tests/roadmap) – Unit tests for models, Jev scoring, prompt/context assembly, and the LLM caller.

**Russell – Connector & Integration**

*MCP connector server*
- [server.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/server.py) – MCP server entry point; installs missing dependencies and starts the server over stdio.
- [tools.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/connectors/tools.py) – MCP tools for fetching applications, nodes, edges, health status, and CSV export.
- [bluedolphin.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/connectors/sources/bluedolphin.py) – BlueDolphin REST client and parser.
- [leanix.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/connectors/sources/leanix.py) – LeanIX GraphQL client and parser.
- [normalize.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/connectors/normalize.py) – Maps source-specific fields into the shared topology schema.
- [topology.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/connectors/topology.py) – Pulls both sources in parallel and merges them into one node/edge topology.
- [resilience.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/connectors/resilience.py) – Timeouts, retries, and circuit breaker so one failing source does not block the other.
- [applications.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/connectors/applications.py) – Builds Application records in the roadmap generator's schema.
- [export.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/mcp/connectors/export.py) – CSV export of applications, dependencies, and other entity tables.
- [README.md](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/mcp/README.md) – Connector setup, MCP tools, output schema, and live-data configuration.
- [tests/mcp](https://github.com/Tony2K3/quantum-ready-capstone/tree/main/code/backend/tests/mcp) – Validates parsing, normalization, merging, resilience, and export using mocked APIs.

*Chat assistant*
- [main.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/chat/app/main.py) – REST API for authentication, sessions, and messages; serves the chat UI.
- [sessions.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/chat/app/sessions.py) – Session lifecycle, ownership checks, chat turns, and history summarization.
- [auth.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/chat/app/auth.py) – User accounts with hashed passwords and bearer tokens.
- [context.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/chat/app/context.py) – Fits conversation history into the model's context window.
- [llm/](https://github.com/Tony2K3/quantum-ready-capstone/tree/main/code/backend/src/chat/app/llm) – Provider-agnostic LLM layer with OpenAI-compatible and Anthropic adapters.
- [storage/](https://github.com/Tony2K3/quantum-ready-capstone/tree/main/code/backend/src/chat/app/storage) – PostgreSQL and SQLite storage backends behind one interface.
- [README.md](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/chat/README.md) – Setup, API reference, configuration, and LLM provider documentation.
- [test_chat.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/chat/test_chat.py) – Validates authentication, session lifecycle, context handling, and the REST API.
- [test_llm.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/chat/test_llm.py) – Validates LLM provider adapters and error handling.

## Retrospective Summary

### Here's what went well:

**Tony:**
- Successfully implemented the core simulation workflow.
- Reused the existing QROS scoring system for consistent results.
- Connected the Python simulation service to the Fastify backend.
- Verified API functionality through local GET and POST requests.

**Peter:**
- Improve coordination with Group 1 for frontend integration.
- Expand test coverage for invalid inputs and edge cases.
- Simplify service setup and dependency management.

**Russell:**


### Here's what we'd like to improve:

**Tony:**
- Improve coordination with Group 1 for frontend integration.
- Expand test coverage for invalid inputs and edge cases.
- Simplify service setup and dependency management.

**Peter:**

**Russell:**


### Here are changes we plan to implement in the next sprint:

**Tony:**
- Integrate the simulator with the frontend.
- Test with real application and infrastructure data.
- Expand supported simulation scenarios.
- Improve automated testing and deployment readiness.

**Peter:**


**Russell:**


