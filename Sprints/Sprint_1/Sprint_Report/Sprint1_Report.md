# Sprint 1 Report – Quantum Ready

**Project:** Quantum Ready  
**Team Members:** Tony Cao, Peter Liu, Russell Habib  
**Sprint Period:** 09/05/2026 – 10/05/2026

## YouTube Link of Sprint 1 Video

[Add unlisted YouTube video link]

## What's New (User Facing)

**Tony – Simulation, Decisioning & Quality (M1)**
- Defined the simulator requirements, including expected inputs, outputs, and constraints.
- Designed a non-destructive simulation architecture to compare current and proposed infrastructure readiness.
- Established how the simulator would integrate with the existing Quantum Ready scoring system.
- Defined the approach for identifying topology relationships and dependencies.

**Peter – AI Reasoning & Roadmap Intelligence**
- Quantum risk scoring across your application portfolio which are ranked by urgency
- AI-generated 30/60/90 day and 2–5 year roadmaps tailored to your role (EA, CTO, CISO)
- Every recommendation traces back to the assessment data that supports it and no new information is generated
- Foundation laid for natural language chat over the generated roadmap


**Russell – Connector & Integration**

- Built the MCP connector for BlueDolphin and LeanIX, mapping their data into the qros topology schema.
-Built the chat bot backend. It’s fully functional and only needs an LLM connection.
-Built a rough chat front end for interacting with the assistant.
-Tested the MCP connector end to end without live API access.

## Work Summary (Developer Facing)

**Tony:**

During Sprint 1, I focused on defining the requirements and designing the initial architecture for the Quantum Ready simulator. I reviewed the existing topology structure, scoring rubric, and assessment process to understand how infrastructure readiness is evaluated. Based on these findings, I designed a simulation workflow that evaluates the current infrastructure, applies proposed modifications to a separate copy of the topology, and compares the resulting assessments without modifying the original data. I also defined the main responsibilities of the simulation engine, including scenario execution, integration with the existing scoring system, and identification of related infrastructure nodes. One important design consideration was ensuring that the simulator reused the existing scoring methodology to maintain consistency across assessments.

**Peter:**

I delivered the core pipeline for the Decision Cortex roadmap generator for this sprint. All input and output data contracts were defined as validated Pydantic models covering enterprise architecture ingestion, priority scoring, and roadmap output. TypeSafe AI’s Jev model was used for per-application quantum priority scoring across five independent dimensions, with applications scored concurrently and mapped to ranked priority objects. A persona based prompt assembly layer was built supporting EA, CTO, and CISO definitions, with Anthropic Claude handling structured roadmap generation backed by schema validation and retry logic. The full pipeline runs end-to-end from enterprise architecture input to a validated roadmap output. Supporting documentation was produced covering the prompt strategy, deterministic vs. LLM responsibilities, and a formal chat context contract defining the MCP tool interface for downstream integration.

**Russell:**

During sprint 1 I made the chat bot backend and rough front end and did  the entirety of the mcp connector. I followed the technical instructions down to a tee. Went pass the sprint requirements for both, the chat bot backend is fully functional and all it needs is a llm connection. The mcp is fully done and tested without api connections as I dont have access to leanix and bluedolphin api keys of my own.
[Russell – Add your work summary here]

## Unfinished Work

**Tony:**
- No unfinished work identified within the assigned M1 requirements and architecture scope.

**Peter:**
- All Sprint 1 responsibilities were completed.

**Russell:**

NA

## Completed Issues/User Stories

**Tony – M1: Simulator Requirements & Architecture**
- Define Simulator Requirements – https://github.com/Tony2K3/quantum-ready-capstone/issues/1
- Design Core Simulation Architecture – https://github.com/Tony2K3/quantum-ready-capstone/issues/2
- Design Scoring System Integration – https://github.com/Tony2K3/quantum-ready-capstone/issues/3
- Design Topology Relationship Handling – https://github.com/Tony2K3/quantum-ready-capstone/issues/4

**Peter:**
- Defined in Clickup

**Russell:**
- Defined in Clickup

## Incomplete Issues/User Stories

**NA**

## Code Files for Review

**Tony – Simulator Architecture**
- [engine.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/engine.py) – Core simulation workflow and assessment comparison design.
- [relationships.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/relationships.py) – Topology relationship and dependency handling.
- [README.md](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/README.md) – Simulator requirements and architecture documentation.
- [demo.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/demo.py) – Demonstrates the simulation workflow using sample topology data.
- [test_engine.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/simulator/test_engine.py) – Validates simulation behavior, topology preservation, and assessment results.
- [test_relationships.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/simulator/test_relationships.py) – Validates topology relationship handling and dependency identification.

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
- Developed a clearer understanding of the existing Quantum Ready topology and scoring system.
- Established the simulator's initial requirements and architecture.
- Designed an approach that preserves the original topology during simulation.
- Identified how to reuse existing assessment functionality.

**Peter:**
- Tested and implemented TypeSafe AI's new Jev model to deterministically give a score for an applications PQC readiness.
- Created an end-to-end pipeline to generate an AI powered roadmap that does not make up information.

**Russell:**

-Finished both the MCP connector and the chat backend, going past the Sprint 1 requirements.
-Followed the technical spec closely, so the connector output fits the existing topology schema.
-Got the connector fully tested even without real API access.

### Here's what we'd like to improve:

**Tony:**
- Improve documentation of simulator inputs, outputs, and edge cases.
- Clarify integration interfaces between the simulator and other backend components.
- Strengthen coordination around shared data structures.

**Peter:**
- Implement a more robust data intake system to handle different MCP connectors.

**Russell:**

-Get access to LeanIX and BlueDolphin API keys or sandboxes so the connector can be tested against real data.
-Connect the chat backend to an LLM and test it with real queries.
-Clean up and improve the chat front end.
-Coordinate more closely with Peter and Tony on how the chat assistant will use the roadmap generator and simulator.

### Here are changes we plan to implement in the next sprint:

**Tony:**
- Refine the simulator's interface specifications.
- Validate the architecture against representative topology examples.
- Improve technical documentation based on team feedback.

**Peter:**
- Roadmap generator core engine & persona prompt chains​
- role-based output refinement​
- EAM input handling​

**Russell:**

- MCP framework
- blue dolphin and leanix connection
  **most of this is already done for the mcp so i will be making it better/testing**
