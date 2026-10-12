# QuantumReady Integration Simulator

## Overview

The Integration Simulator provides a view-only environment for evaluating how a proposed change to an enterprise system may affect its quantum-readiness posture.

The simulator uses the existing QuantumReady OS (QROS) topology model, scoring engine, and scoring rubric. It does not modify the original topology. Instead, it creates a copy of the current topology, applies a hypothetical change to the copy, reassesses it using QROS, and compares the current and proposed states.

The simulator also performs dependency analysis using the connections defined in the topology so that a change to one selected system can be viewed in the context of other related systems.

---

## M1 Scope

Milestone 1 focuses on defining the **Simulator Requirements and Architecture**.

The goals of M1 are to:

- Define what a simulation represents.
- Define the required simulator inputs and outputs.
- Establish a view-only simulation architecture.
- Reuse the existing QROS scoring engine rather than creating a separate scoring system.
- Identify systems that may be affected by a proposed change through topology relationships.
- Validate the architecture through a working proof of concept.

The current implementation provides a working POC for these requirements.

---

## Simulator Requirements

### Inputs

The simulator currently requires:

- A valid QROS topology YAML file.
- A QROS scoring rubric.
- A selected node/application from the topology.
- A simulation scenario.

The current POC implements a **PQC hardening** scenario.

### Outputs

The simulator produces:

- Current readiness score.
- Proposed readiness score.
- Readiness score delta.
- Current failing findings.
- Proposed failing findings.
- Finding delta.
- Current and proposed pillar scores.
- Critical-cap status.
- Directly related systems.
- Reachable systems that may be within the dependency impact scope.

### Constraints

The simulator follows several important constraints:

- Simulations are view-only.
- The original topology must not be modified.
- Proposed changes are applied to a deep copy of the topology.
- Current and proposed states must use the same QROS scoring engine and rubric.
- Simulation results should remain explainable through QROS findings and pillar scores.
- Dependency results currently represent potential impact scope rather than guaranteed technical impact.

---

## Architecture

The current simulator follows this flow:

```text
                 QROS Topology YAML
                         |
                         v
                  Load Topology
                         |
             +-----------+-----------+
             |                       |
             v                       v
      Current Topology        Dependency Analysis
             |                       |
             v                       v
       QROS Assessment       Direct Dependencies
             |               Reachable Systems
             |
             v
      Current Assessment
             |
             v
       Deep Copy Topology
             |
             v
   Apply Simulation Scenario
      (PQC Hardening)
             |
             v
       Proposed Topology
             |
             v
       QROS Assessment
             |
             v
      Proposed Assessment
             |
             v
       Compare Results
             |
             v
   +---------------------------+
   | Readiness Score Delta     |
   | Finding Delta             |
   | Pillar Comparison         |
   | Critical Cap              |
   | Dependency Impact Scope   |
   +---------------------------+
```

The simulator intentionally relies on QROS for assessment logic. This keeps the scoring methodology consistent between normal assessments and simulated states.

---

## Current PQC Hardening Scenario

The current proof-of-concept scenario applies hypothetical PQC-related changes to a selected node.

Depending on the node configuration, the scenario can modify properties such as:

- TLS version.
- PQC-capable key exchange.
- PQC capability of cryptographic libraries.
- Key-management configuration.
- Key-rotation policy.
- Crypto-agility.
- PQC migration planning.

These changes are made only to the copied topology.

The modified topology is then reassessed using the same QROS rubric.

---

## Dependency Impact Analysis

Applications and infrastructure components do not necessarily operate independently. A change to one system may need to be evaluated together with connected systems.

The simulator therefore uses the `connections` defined in the QROS topology to identify:

1. **Directly related systems** — nodes directly connected to the selected node.
2. **Reachable systems** — nodes that can be reached through additional topology connections.

For example:

```text
edge-gw-01
    |
    v
core-cloud-01
    |
    v
qnode-lab-01
```

Selecting `edge-gw-01` identifies:

```text
Directly related:
- core-cloud-01

Reachable:
- core-cloud-01
- qnode-lab-01
```

At the current M1 stage, reachable systems represent the **potential dependency/impact scope**. Additional rules may later determine whether a connected system is actually affected by a specific type of proposed change.

---

## Example Output

A simulation against the current sample topology may produce output similar to:

```text
============================================================
QUANTUMREADY INTEGRATION SIMULATOR
============================================================

Scenario: pqc-hardening
Selected node: edge-gw-01

DEPENDENCY IMPACT
------------------------------------------------------------
Directly related systems: 1
  - core-cloud-01

Total reachable systems: 2
  - core-cloud-01
  - qnode-lab-01

READINESS COMPARISON
------------------------------------------------------------
Current score:  63.2
Proposed score: 84.8
Score delta:    +21.6

FINDINGS
------------------------------------------------------------
Current failing findings:  14
Proposed failing findings: 7
Finding delta:             -7

PILLAR COMPARISON
------------------------------------------------------------
compute          76.7 ->   90.0   (+13.3)
network          73.3 ->  100.0   (+26.7)
security         46.7 ->   75.0   (+28.3)
governance       53.3 ->   65.0   (+11.7)

CRITICAL CAP
------------------------------------------------------------
Current state:  NO
Proposed state: NO

============================================================
Simulation only — the original topology was not modified.
============================================================
```

---

# Running the Simulator

## Prerequisites

The simulator requires Python 3.10 or newer.

Verify the Python version:

```bash
python3 --version
```

The simulator also depends on the local `quantumready-os` package.

An example repository structure is:

```text
quantinnel/
├── apps/
│   └── decision-cortex/
│       └── src/
│           └── simulator/
│               ├── engine.py
│               ├── demo.py
│               └── README.md
│
└── quantumready-os/
    ├── examples/
    │   └── example_topology.yaml
    └── qros/
        └── rubric_data/
            └── rubric_v1.yaml
```

---

## Install QuantumReady OS

From the `decision-cortex` directory, install the local QROS package:

```bash
python3 -m pip install -e ../../quantumready-os
```

If a virtual environment is being used, activate it before installing the package.

Verify that QROS can be imported:

```bash
python3 -c "import qros; print('QROS installed successfully')"
```

---

## Run the Simulator

From:

```text
quantinnel/apps/decision-cortex
```

run:

```bash
python3 -m src.simulator.demo \
  ../../quantumready-os/examples/example_topology.yaml \
  --rubric ../../quantumready-os/qros/rubric_data/rubric_v1.yaml \
  --node edge-gw-01
```

If the local environment uses `python` instead of `python3`, the equivalent command is:

```bash
python -m src.simulator.demo \
  ../../quantumready-os/examples/example_topology.yaml \
  --rubric ../../quantumready-os/qros/rubric_data/rubric_v1.yaml \
  --node edge-gw-01
```

---

## Selecting Another Node

The `--node` argument determines which topology node will be used for the hypothetical simulation.

For example:

```bash
python3 -m src.simulator.demo \
  ../../quantumready-os/examples/example_topology.yaml \
  --rubric ../../quantumready-os/qros/rubric_data/rubric_v1.yaml \
  --node core-cloud-01
```

The node must exist in the supplied topology.

---

## Current Assumptions

The M1 implementation currently makes the following assumptions:

- QROS is the source of truth for readiness scoring.
- Simulation changes should never modify the original topology.
- A simulation compares the same topology before and after a hypothetical change.
- Topology connections can be used to identify potential dependency impact.
- Reachability does not automatically mean that a system is technically impacted.
- More detailed impact-propagation rules can be introduced as simulator requirements are refined.

---

## Future Work

The following work is outside the primary M1 requirements and will continue in later milestones:

- Additional simulation scenarios.
- Scenario library.
- Automated regression tests.
- More detailed dependency-impact rules.
- Integration with connector data.
- Integration with other backend outputs.
- Chat/user interface integration.
- Frontend visualization of simulation results.
- End-to-end pipeline testing.
- Staging and final demonstration.

---

## M1 Status

**M1 – Simulator Requirements & Architecture: Complete**

The simulator requirements and architecture have been defined and validated through a working proof of concept.

The current implementation demonstrates:

- View-only what-if simulation.
- Current vs. proposed readiness assessment.
- Reuse of the QROS scoring engine.
- Readiness score comparison.
- Finding comparison.
- Pillar-level comparison.
- Dependency/reachability analysis.
- Protection of the original topology through deep-copy simulation.

Further simulator functionality and integration will be developed as part of subsequent milestones.


## M1 Validation and Testing

The Integration Simulator includes automated tests to validate
the M1 proof of concept and its integration with QROS.

### Test Structure

- `tests/simulator/test_engine.py`
  - Valid and invalid node simulation
  - Original topology immutability
  - Deep-copy behavior
  - PQC-hardening configuration changes
  - Current and proposed readiness scores
  - Findings and score delta calculations
  - Integration with the QROS scoring engine

- `tests/simulator/test_relationships.py`
  - Direct dependency detection
  - Reachable system discovery
  - Exclusion of the selected node
  - Duplicate prevention
  - Isolated nodes
  - Cyclic topology handling

### Running Tests

From `apps/decision-cortex`:

```bash
python3 -m pip install -e ../../quantumready-os
python3 -m pip install pytest
python3 -m pytest tests/simulator/ -v
```

Run lint checks:

```bash
ruff check src/simulator/ tests/simulator/
```

### M1 Validation Status

All 17 M1 validation tests pass.

The tests cover the simulation engine, QROS scoring integration,
topology immutability, PQC hardening, and dependency analysis.

### Current Limitations

- The initial scenario focuses on PQC hardening.
- Dependency reachability indicates potential impact scope,
  not confirmed propagation of technical changes.
- Full scenario regression testing is planned for M2.
- End-to-end pipeline validation and CI enforcement are
  planned for later milestones.
