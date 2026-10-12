"""
Tests for Pydantic model validation.

Covers Application, Connection, EnterpriseArchitecture, and
ApplicationPriority schema validation — valid cases, required field
enforcement, enum constraints, and cross-model validators.
"""

import pytest
from pydantic import ValidationError

from src.roadmap.models.application import Application
from src.roadmap.models.connection import Connection
from src.roadmap.models.enterprise_architecture import EnterpriseArchitecture
from src.roadmap.models.priority import ApplicationPriority

# Helpers

def make_application(**overrides) -> Application:
    defaults = {
        "id": "APP-001",
        "name": "Payment Service",
    }
    defaults.update(overrides)
    return Application(**defaults)


def make_connection(**overrides) -> Connection:
    defaults = {
        "source_application_id": "APP-001",
        "target_application_id": "APP-002",
        "relationship": "API",
    }
    defaults.update(overrides)
    return Connection(**defaults)


def make_priority(**overrides) -> ApplicationPriority:
    defaults = {
        "application_id": "APP-001",
        "application_name": "Payment Service",
        "priority_level": "High",
        "priority_score": 72.5,
        "key_factors": ["APP-001.business_criticality = High"],
    }
    defaults.update(overrides)
    return ApplicationPriority(**defaults)


# Application

class TestApplicationModel:

    def test_minimal_valid_application(self):
        app = make_application()
        assert app.id == "APP-001"
        assert app.name == "Payment Service"

    def test_all_optional_fields_default_to_none(self):
        app = make_application()
        assert app.business_criticality is None
        assert app.data_sensitivity is None
        assert app.data_longevity is None
        assert app.vendor_dependency is None
        assert app.owner is None
        assert app.deployment_environment is None
        assert app.network_protocols is None
        assert app.network_exposure is None
        assert app.crypto_agility is None
        assert app.key_management_type is None
        assert app.cryptographic_dependencies is None
        assert app.pqc_readiness is None
        assert app.extra_attributes is None

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            Application(name="Payment Service")

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            Application(id="APP-001")

    def test_invalid_business_criticality_raises(self):
        with pytest.raises(ValidationError):
            make_application(business_criticality="Extreme")

    def test_invalid_data_sensitivity_raises(self):
        with pytest.raises(ValidationError):
            make_application(data_sensitivity="Secret")

    def test_invalid_data_longevity_raises(self):
        with pytest.raises(ValidationError):
            make_application(data_longevity="Forever")

    def test_invalid_network_exposure_raises(self):
        with pytest.raises(ValidationError):
            make_application(network_exposure="External")

    def test_invalid_key_management_type_raises(self):
        with pytest.raises(ValidationError):
            make_application(key_management_type="Unknown")

    def test_invalid_pqc_readiness_raises(self):
        with pytest.raises(ValidationError):
            make_application(pqc_readiness="In Progress")

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            make_application(nonexistent_field="value")

    def test_fully_populated_application_valid(self):
        app = make_application(
            business_criticality="High",
            data_sensitivity="High",
            data_longevity="Long",
            vendor_dependency="Medium",
            owner="Payments Team",
            deployment_environment="Cloud",
            network_protocols=["TLS 1.3"],
            network_exposure="Public",
            crypto_agility=True,
            key_management_type="KMS",
            cryptographic_dependencies=["OpenSSL 3.4", "ML-KEM-768"],
            pqc_readiness="Partial",
            technology_stack="Java",
            description="Handles payment processing.",
            business_unit="Finance",
        )
        assert app.business_criticality == "High"
        assert app.key_management_type == "KMS"


# Connection

class TestConnectionModel:

    def test_valid_connection_passes(self):
        conn = make_connection()
        assert conn.source_application_id == "APP-001"
        assert conn.target_application_id == "APP-002"

    def test_self_reference_raises(self):
        with pytest.raises(ValidationError):
            make_connection(
                source_application_id="APP-001",
                target_application_id="APP-001",
            )

    def test_optional_fields_default_to_none(self):
        conn = make_connection()
        assert conn.dependency_type is None
        assert conn.criticality is None
        assert conn.description is None

    def test_invalid_relationship_type_raises(self):
        with pytest.raises(ValidationError):
            make_connection(relationship="Telepathy")

    def test_invalid_dependency_type_raises(self):
        with pytest.raises(ValidationError):
            make_connection(dependency_type="Maybe")

    def test_all_relationship_types_valid(self):
        valid_types = [
            "API", "Database", "Message Queue",
            "File Transfer", "Authentication", "Service Dependency", "Other",
        ]
        for rel in valid_types:
            conn = make_connection(relationship=rel)
            assert conn.relationship == rel

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            make_connection(nonexistent_field="value")


# EnterpriseArchitecture

class TestEnterpriseArchitectureModel:

    def test_valid_architecture_with_no_connections(self):
        arch = EnterpriseArchitecture(
            applications=[make_application()],
            connections=[],
        )
        assert len(arch.applications) == 1
        assert len(arch.connections) == 0

    def test_empty_connections_is_default(self):
        arch = EnterpriseArchitecture(applications=[make_application()])
        assert arch.connections == []

    def test_valid_architecture_with_connections(self):
        app1 = make_application(id="APP-001")
        app2 = make_application(id="APP-002", name="Customer Portal")
        conn = make_connection(
            source_application_id="APP-001",
            target_application_id="APP-002",
        )
        arch = EnterpriseArchitecture(applications=[app1, app2], connections=[conn])
        assert len(arch.connections) == 1

    def test_connection_with_unknown_source_raises(self):
        app = make_application(id="APP-001")
        conn = make_connection(
            source_application_id="APP-999",
            target_application_id="APP-001",
        )
        with pytest.raises(ValidationError):
            EnterpriseArchitecture(applications=[app], connections=[conn])

    def test_connection_with_unknown_target_raises(self):
        app = make_application(id="APP-001")
        conn = make_connection(
            source_application_id="APP-001",
            target_application_id="APP-999",
        )
        with pytest.raises(ValidationError):
            EnterpriseArchitecture(applications=[app], connections=[conn])

    def test_multiple_applications_valid(self):
        apps = [
            make_application(id=f"APP-00{i}", name=f"App {i}")
            for i in range(1, 5)
        ]
        arch = EnterpriseArchitecture(applications=apps)
        assert len(arch.applications) == 4


# ApplicationPriority

class TestApplicationPriorityModel:

    def test_valid_priority_passes(self):
        p = make_priority()
        assert p.application_id == "APP-001"
        assert p.priority_level == "High"
        assert p.priority_score == 72.5

    def test_invalid_priority_level_raises(self):
        with pytest.raises(ValidationError):
            make_priority(priority_level="Urgent")

    def test_all_priority_levels_valid(self):
        for level in ("Critical", "High", "Medium", "Low"):
            p = make_priority(priority_level=level)
            assert p.priority_level == level

    def test_missing_fields_default_to_empty_list(self):
        p = make_priority()
        assert p.critical_check_failures == []
        assert p.missing_fields == []

    def test_key_factors_preserved(self):
        factors = [
            "APP-001.business_criticality = High",
            "APP-001.data_longevity = Long",
        ]
        p = make_priority(key_factors=factors)
        assert p.key_factors == factors
