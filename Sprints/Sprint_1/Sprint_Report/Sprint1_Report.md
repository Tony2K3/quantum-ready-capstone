# Sprint 1 Report – Quantum Ready

**Project:** Quantum Ready  
**Team Members:** Tony Cao, Peter Liu, Russell Habib  
**Sprint Period:** [Start Date] – [End Date]

## YouTube Link of Sprint 1 Video

[Add unlisted YouTube video link]

## What's New (User Facing)

**Tony – Simulation, Decisioning & Quality (M1)**
- Defined the simulator requirements, including expected inputs, outputs, and constraints.
- Designed a non-destructive simulation architecture to compare current and proposed infrastructure readiness.
- Established how the simulator would integrate with the existing Quantum Ready scoring system.
- Defined the approach for identifying topology relationships and dependencies.

**Peter – AI Reasoning & Roadmap Intelligence**
- [Peter – Add your Sprint 1 contributions here]

**Russell – Connector & Integration**
- [Russell – Add your Sprint 1 contributions here]

## Work Summary (Developer Facing)

**Tony:**

During Sprint 1, I focused on defining the requirements and designing the initial architecture for the Quantum Ready simulator. I reviewed the existing topology structure, scoring rubric, and assessment process to understand how infrastructure readiness is evaluated. Based on these findings, I designed a simulation workflow that evaluates the current infrastructure, applies proposed modifications to a separate copy of the topology, and compares the resulting assessments without modifying the original data. I also defined the main responsibilities of the simulation engine, including scenario execution, integration with the existing scoring system, and identification of related infrastructure nodes. One important design consideration was ensuring that the simulator reused the existing scoring methodology to maintain consistency across assessments.

**Peter:**

[Peter – Add your work summary here]

**Russell:**

[Russell – Add your work summary here]

## Unfinished Work

**Tony:**
- No unfinished work identified within the assigned M1 requirements and architecture scope.

**Peter:**
- [Peter – Add unfinished work, if applicable]

**Russell:**
- [Russell – Add unfinished work, if applicable]

## Completed Issues/User Stories

**Tony – M1: Simulator Requirements & Architecture**
- Define Simulator Requirements – https://github.com/Tony2K3/quantum-ready-capstone/issues/1
- Design Core Simulation Architecture – https://github.com/Tony2K3/quantum-ready-capstone/issues/2
- Design Scoring System Integration – https://github.com/Tony2K3/quantum-ready-capstone/issues/3
- Design Topology Relationship Handling – https://github.com/Tony2K3/quantum-ready-capstone/issues/4

**Peter:**
- [Peter – Add completed issues and links]

**Russell:**
- [Russell – Add completed issues and links]

## Incomplete Issues/User Stories

**Tony:**
- None identified within the M1 scope.

**Peter:**
- [Peter – Add incomplete issues and explanations, if applicable]

**Russell:**
- [Russell – Add incomplete issues and explanations, if applicable]

## Code Files for Review

**Tony – Simulator Architecture**
- [engine.py] (https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/engine.py) – Core simulation workflow and assessment comparison design.
- [relationships.py](https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/demo.py) – Topology relationship and dependency handling.
- [README.md] (https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/README.md) – Simulator requirements and architecture documentation.
- [demo.py] (https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/demo.py) – Demonstrates the simulation workflow using sample topology data.
- [test_engine.py] (https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/simulator/test_engine.py) – Validates simulation behavior, topology preservation, and assessment results.
- [test_relationships.py] (https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/simulator/test_relationships.py) – Validates topology relationship handling and dependency identification.

- https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/demo.py
- https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/relationships.py
- https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/src/simulator/README.md
- https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/simulator/test_engine.py
- https://github.com/Tony2K3/quantum-ready-capstone/blob/main/code/backend/tests/simulator/test_relationships.py

**Peter:**
- [Peter – Add code files and GitHub links]

**Russell:**
- [Russell – Add code files and GitHub links]

## Retrospective Summary

### Here's what went well:

**Tony:**
- Developed a clearer understanding of the existing Quantum Ready topology and scoring system.
- Established the simulator's initial requirements and architecture.
- Designed an approach that preserves the original topology during simulation.
- Identified how to reuse existing assessment functionality.

**Peter:**
- [Peter – Add what went well]

**Russell:**
- [Russell – Add what went well]

### Here's what we'd like to improve:

**Tony:**
- Improve documentation of simulator inputs, outputs, and edge cases.
- Clarify integration interfaces between the simulator and other backend components.
- Strengthen coordination around shared data structures.

**Peter:**
- [Peter – Add areas for improvement]

**Russell:**
- [Russell – Add areas for improvement]

### Here are changes we plan to implement in the next sprint:

**Tony:**
- Refine the simulator's interface specifications.
- Validate the architecture against representative topology examples.
- Improve technical documentation based on team feedback.

**Peter:**
- [Peter – Add next sprint plans]

**Russell:**
- [Russell – Add next sprint plans]