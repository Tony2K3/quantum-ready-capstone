"""
Lookup tables from source-system values to model values.

Unknown values are never guessed: adapters keep them in `extra_attributes`
and report a warning.
"""

from __future__ import annotations

from ..roadmap.models.application import DeploymentEnvironment, HostingType
from ..roadmap.models.provenance import LifecyclePhase

# LeanIX

LEANIX_BUSINESS_CRITICALITY: dict[str, str] = {
    "missionCritical": "High",
    "businessCritical": "High",
    "businessOperational": "Medium",
    "administrativeService": "Low",
}

LEANIX_HOSTING_TYPE: dict[str, str] = {
    "saas": "SaaS",
    "paas": "PaaS",
    "iaas": "IaaS",
    "onPremise": "On-Premise",
    "hybrid": "Hybrid",
    "desktopOrLaptop": "Desktop",
    "mobile": "Mobile",
}

LEANIX_TIME_CLASSIFICATION: dict[str, str] = {
    "Tolerate": "Tolerate",
    "Invest": "Invest",
    "Migrate": "Migrate",
    "Eliminate": "Eliminate",
}

LEANIX_TECHNICAL_FIT: dict[str, str] = {
    "inappropriate": "Inappropriate",
    "unreasonable": "Unreasonable",
    "adequate": "Adequate",
    "fullyAppropriate": "Fully Appropriate",
}

LEANIX_INTERFACE_TYPE: dict[str, str] = {
    "synchronous": "API",
    "asynchronous": "Message Queue",
    "batch": "File Transfer",
}

LEANIX_FREQUENCY: dict[str, str] = {
    "realtime": "Real-time",
    "hourly": "Hourly",
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
    "onDemand": "On Demand",
}

LEANIX_DATA_FLOW_DIRECTION: dict[str, str] = {
    "incoming": "unidirectional",
    "outgoing": "unidirectional",
    "biDirectional": "bidirectional",
}

LEANIX_LIFECYCLE: dict[str, LifecyclePhase] = {
    "plan": "Plan",
    "phaseIn": "Phase In",
    "active": "Active",
    "phaseOut": "Phase Out",
    "endOfLife": "End of Life",
}

# Model-level derivations

HOSTING_TO_DEPLOYMENT: dict[HostingType, DeploymentEnvironment | None] = {
    "SaaS": "Cloud",
    "PaaS": "Cloud",
    "IaaS": "Cloud",
    "On-Premise": "On-Premise",
    "Hybrid": "Hybrid",
    "Desktop": "On-Premise",
    "Mobile": None,
}

# Native CSV lifecycle date columns

CSV_LIFECYCLE_COLUMNS: dict[str, LifecyclePhase] = {
    "lifecycle_plan": "Plan",
    "lifecycle_phase_in": "Phase In",
    "lifecycle_active": "Active",
    "lifecycle_phase_out": "Phase Out",
    "lifecycle_end_of_life": "End of Life",
}
