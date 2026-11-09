"""
Application input schema for the Decision Cortex roadmap generator.

All fields except `id` and `name` are optional.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .provenance import FieldSource, LifecyclePhase, SourceSystem

# Type aliases for categorical fields

BusinessCriticality = Literal["Low", "Medium", "High"]
DataSensitivity = Literal["Low", "Medium", "High"]
DataLongevity = Literal["Short", "Medium", "Long"]
VendorDependency = Literal["Low", "Medium", "High"]

DeploymentEnvironment = Literal["Cloud", "On-Premise", "Hybrid"]
NetworkExposure = Literal["Public", "Internal", "Isolated"]
KeyManagementType = Literal["HSM", "KMS", "Software", "None"]
PQCReadiness = Literal["Not Assessed", "Not Ready", "Partial", "Ready"]

HostingType = Literal["SaaS", "PaaS", "IaaS", "On-Premise", "Hybrid", "Desktop", "Mobile"]
TimeClassification = Literal["Tolerate", "Invest", "Migrate", "Eliminate"]
TechnicalFit = Literal["Inappropriate", "Unreasonable", "Adequate", "Fully Appropriate"]

# Fields whose provenance is tracked in `field_sources` and reported on by
# the normalizer. Identity fields, free text and passthrough data are excluded.
TRACKED_FIELDS: tuple[str, ...] = (
    "business_unit",
    "owner",
    "business_criticality",
    "data_sensitivity",
    "data_longevity",
    "vendor_dependency",
    "technology_stack",
    "deployment_environment",
    "hosting_type",
    "lifecycle_status",
    "time_classification",
    "technical_fit",
    "cryptographic_dependencies",
    "pqc_readiness",
    "network_protocols",
    "network_exposure",
    "crypto_agility",
    "key_management_type",
    "it_components",
    "data_objects",
)


class Application(BaseModel):
    """
    A single enterprise application as received from a connector or CSV import.

    Only `id` and `name` are required. All other fields are optional to
    accommodate connectors that do not export every attribute.
    """

    id: str = Field(
        description=(
            "Unique application identifier assigned by the connector "
            "(e.g. 'APP-001'). Must be stable across imports to allow "
            "roadmap versioning and change tracking."
        )
    )
    name: str = Field(
        description="Application name."
    )
    description: str | None = Field(
        default=None,
        description="Brief description of the application's purpose."
    )
    business_unit: str | None = Field(
        default=None,
        description="Business unit or department that owns this application."
    )
    owner: str | None = Field(
        default=None,
        description=(
            "Named owner or owning team responsible for this application. "
            "Used to assign roadmap actions. Missing owner is a gap the "
            "roadmap generator should flag."
        )
    )

    # Risk factors
    # These fields drive prioritisation scoring and are optional.

    business_criticality: BusinessCriticality | None = Field(
        default=None,
        description=(
            "How critical this application is to business operations. "
            "None = not assessed or not provided by the connector."
        )
    )
    data_sensitivity: DataSensitivity | None = Field(
        default=None,
        description=(
            "Sensitivity of the data this application processes or stores "
            "(e.g. PII, financial, regulated). "
            "None = not assessed or not provided by the connector."
        )
    )
    data_longevity: DataLongevity | None = Field(
        default=None,
        description=(
            "How long the data handled by this application must remain confidential. "
            "None = not assessed or not provided by the connector."
        )
    )
    vendor_dependency: VendorDependency | None = Field(
        default=None,
        description=(
            "Degree to which PQC migration depends on an external vendor's "
            "roadmap or support. High vendor dependency may constrain "
            "migration timelines. "
            "None = not assessed or not provided by the connector."
        )
    )

    # Technical Context

    technology_stack: str | None = Field(
        default=None,
        description=(
            "Primary technology platform, language, or framework "
            "(free text as provided by the connector)."
        )
    )
    deployment_environment: DeploymentEnvironment | None = Field(
        default=None,
        description=(
            "Where the application is hosted. "
            "ASSUMPTION: availability from connector not yet confirmed."
        )
    )
    cryptographic_dependencies: list[str] | None = Field(
        default=None,
        description=(
            "Known cryptographic algorithms or libraries in use "
            "(e.g. ['RSA-2048', 'TLS 1.2', 'AES-CBC']). "
            "ASSUMPTION: this may come from the EA connector, from the "
            "internal quantum model, or from both. Source to be confirmed "
            "before the contract is finalised."
        )
    )
    pqc_readiness: PQCReadiness | None = Field(
        default=None,
        description=(
            "Current PQC readiness state if already assessed. "
            "ASSUMPTION: this may be an EA-system attribute or an output of the "
            "internal quantum model. Source to be confirmed."
        )
    )
    network_protocols: list[str] | None = Field(
        default=None,
        description=(
            "Network protocols this application exposes or uses, including version "
            "where known (e.g. ['TLS 1.2', 'TLS 1.3', 'SSH 2']). "
            "Used to evaluate protocol-level quantum exposure in the scoring engine. "
            "None = not provided by connector."
        )
    )
    network_exposure: NetworkExposure | None = Field(
        default=None,
        description=(
            "Whether this application is publicly reachable, internal-only, or isolated. "
            "Public applications with weak protocols are highest priority for PQC migration. "
            "None = not provided by connector; scoring engine will infer from "
            "business_criticality as a fallback."
        )
    )
    crypto_agility: bool | None = Field(
        default=None,
        description=(
            "Whether the cryptographic algorithms used by this application can be "
            "swapped without re-architecting it. Crypto-agile applications are "
            "significantly easier to migrate. "
            "None = not assessed or not provided by connector."
        )
    )
    key_management_type: KeyManagementType | None = Field(
        default=None,
        description=(
            "How cryptographic keys are managed for this application. "
            "HSM and KMS are preferred; Software and None are higher risk. "
            "None = not assessed or not provided by connector."
        )
    )

    # Portfolio context (from EA tools)

    hosting_type: HostingType | None = Field(
        default=None,
        description=(
            "Hosting model as recorded in the EA tool. More detailed than "
            "deployment_environment, which is derived from it when not provided."
        )
    )
    lifecycle_status: LifecyclePhase | None = Field(
        default=None,
        description=(
            "Lifecycle phase in effect at import time. Planned or retiring "
            "applications should not be prioritised like live ones."
        )
    )
    lifecycle_dates: dict[LifecyclePhase, date] | None = Field(
        default=None,
        description="Start date of each known lifecycle phase."
    )
    time_classification: TimeClassification | None = Field(
        default=None,
        description="Gartner TIME classification (Tolerate, Invest, Migrate, Eliminate)."
    )
    technical_fit: TechnicalFit | None = Field(
        default=None,
        description="How well the application's technology suits its purpose."
    )
    it_components: list[str] | None = Field(
        default=None,
        description="Underlying technology components (platforms, databases, middleware)."
    )
    data_objects: list[str] | None = Field(
        default=None,
        description=(
            "Business data objects this application exchanges (e.g. 'Customer', "
            "'Price'). Taken from its interfaces when not provided directly."
        )
    )

    # Provenance

    source_system: SourceSystem | None = Field(
        default=None,
        description=(
            "System this record was imported from. 'placeholder' means the "
            "application was only referenced by an interface and has no record of its own."
        )
    )
    source_id: str | None = Field(
        default=None,
        description="The record's identifier in the source system (e.g. the LeanIX fact sheet id)."
    )
    field_sources: dict[str, FieldSource] = Field(
        default_factory=dict,
        description=(
            "Where each tracked field's value came from, keyed by field name. "
            "See TRACKED_FIELDS."
        )
    )

    # Connector passthrough

    extra_attributes: dict[str, str | list[str]] | None = Field(
        default=None,
        description=(
            "Catch-all for additional EA attributes provided by the connector "
            "that do not map to a named field above. "
        )
    )

    # Reject unexpected fields from the connector rather than silently dropping them
    model_config = ConfigDict(extra="forbid")
