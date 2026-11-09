"""
Tests for the LeanIX adapter and the shared assemble() step.

Fixtures are synthetic LeanIX-style workbooks built in tmp_path.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.ingest import NormalizationError, normalize
from src.ingest.report import NormalizationResult
from src.roadmap.models.application import TRACKED_FIELDS, Application

AS_OF = date(2026, 11, 8)
CRYPTO_FIELDS = ("cryptographic_dependencies", "network_protocols", "crypto_agility", "key_management_type")


def app_row(name: str, **fields: object) -> dict[str, object]:
    return {"type": "Application", "name": name, **fields}


def interface_row(name: str, provider: str | None, consumer: str | None, **fields: object) -> dict[str, object]:
    row: dict[str, object] = {"type": "Interface", "name": name, **fields}
    if provider is not None:
        row["relInterfaceToProviderApplication"] = provider
    if consumer is not None:
        row["relInterfaceToConsumerApplication"] = consumer
    return row


def run(*paths: Path, **kwargs: object) -> NormalizationResult:
    return normalize([("leanix", list(paths))], as_of=AS_OF, **kwargs)  # type: ignore[arg-type]


def app_by_name(result: NormalizationResult, name: str) -> Application:
    return next(a for a in result.architecture.applications if a.name == name)


def codes(result: NormalizationResult, severity: str | None = None) -> list[str]:
    return [i.code for i in result.report.issues if severity is None or i.severity == severity]


# Reading files

class TestReadingFiles:

    def test_uses_key_row_and_skips_label_row_and_readme(self, write_leanix):
        path = write_leanix("apps.xlsx", [app_row("Billing", description="Bills customers")])
        result = run(path)
        assert [a.name for a in result.architecture.applications] == ["Billing"]
        assert result.report.files[0].rows == 1

    def test_detects_record_types_from_type_column(self, write_leanix, tmp_path):
        write_leanix("apps.xlsx", [app_row("Billing"), app_row("Ledger")])
        write_leanix("interfaces.xlsx", [interface_row("INT-001 · Ledger → Billing", "Ledger", "Billing")])
        result = run(tmp_path)
        assert len(result.architecture.applications) == 2
        assert len(result.architecture.connections) == 1

    def test_unsupported_types_are_skipped_and_reported(self, write_leanix, tmp_path):
        write_leanix("apps.xlsx", [app_row("Billing")])
        write_leanix("caps.xlsx", [{"type": "BusinessCapability", "name": "Order to cash"}])
        result = run(tmp_path)
        skipped = next(f for f in result.report.files if f.path.endswith("caps.xlsx"))
        assert skipped.status == "skipped"
        assert "BusinessCapability" in (skipped.message or "")
        assert [a.name for a in result.architecture.applications] == ["Billing"]

    def test_templates_are_skipped_unless_requested(self, write_leanix, tmp_path):
        write_leanix("apps.xlsx", [app_row("Billing")])
        write_leanix("ApplicationTemplate.xlsx", [app_row("Example Application")])
        assert [a.name for a in run(tmp_path).architecture.applications] == ["Billing"]
        included = run(tmp_path, include_templates=True)
        assert {a.name for a in included.architecture.applications} == {"Billing", "Example Application"}

    def test_list_values_are_split_on_semicolons(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("Billing"), app_row("Ledger"),
            interface_row(
                "INT-001 · Ledger → Billing", "Ledger", "Billing",
                relInterfaceToITComponent="Boomi SaaS Hosting;MVIS service tier",
            ),
        ])
        conn = run(path).architecture.connections[0]
        assert conn.via == ["Boomi SaaS Hosting", "MVIS service tier"]

    @pytest.mark.parametrize("raw, expected", [
        (44197, date(2021, 1, 1)),
        ("44779", date(2022, 8, 6)),
        ("2026-08-19", date(2026, 8, 19)),
    ])
    def test_lifecycle_dates_accept_excel_serials_and_iso(self, write_leanix, raw, expected):
        path = write_leanix("apps.xlsx", [app_row("Billing", **{"lifecycle:active": raw})])
        app = run(path).architecture.applications[0]
        assert app.lifecycle_dates == {"Active": expected}
        assert app.lifecycle_status == "Active"

    def test_invalid_date_is_reported_and_ignored(self, write_leanix):
        path = write_leanix("apps.xlsx", [app_row("Billing", **{"lifecycle:active": "next spring"})])
        result = run(path)
        assert result.architecture.applications[0].lifecycle_dates is None
        assert "invalid_date" in codes(result, "warning")

    def test_unreadable_file_does_not_stop_the_import(self, write_leanix, tmp_path):
        write_leanix("apps.xlsx", [app_row("Billing")])
        (tmp_path / "broken.xlsx").write_bytes(b"not a workbook")
        result = run(tmp_path)
        assert [a.name for a in result.architecture.applications] == ["Billing"]
        broken = next(f for f in result.report.files if f.path.endswith("broken.xlsx"))
        assert broken.status == "error"
        assert "unreadable_file" in codes(result, "error")

    def test_no_applications_raises_with_report(self, write_leanix):
        path = write_leanix("caps.xlsx", [{"type": "BusinessCapability", "name": "Order to cash"}])
        with pytest.raises(NormalizationError, match="No applications found") as exc_info:
            run(path)
        assert exc_info.value.report.application_count == 0


# Merging and identity

class TestMergingAndIds:

    def test_numbered_update_files_override_earlier_files(self, write_leanix, tmp_path):
        write_leanix("apps.xlsx", [app_row("Pricing"), app_row("CPQ"), app_row("M-Price")])
        write_leanix("Export_Interfaces.xlsx", [interface_row(
            "INT-002 · M-Price → CPQ · Price", "M-Price", "CPQ", id="iface-2"
        )])
        write_leanix("07_Update_Interfaces.xlsx", [interface_row(
            "INT-002 · Pricing → CPQ · Price", "Pricing", "CPQ", id="iface-2"
        )])
        result = run(tmp_path)
        conns = [c for c in result.architecture.connections if c.interface_id == "INT-002"]
        assert len(conns) == 1
        assert conns[0].name == "INT-002 · Pricing → CPQ · Price"
        assert conns[0].target_application_id == app_by_name(result, "Pricing").id
        assert "merged_record" in codes(result, "info")

    @pytest.mark.parametrize("first, second", [
        ({"id": "abc"}, {"id": "abc", "name": "INT-900 renamed"}),
        ({"externalId": "x1;x2"}, {"externalId": "x2", "name": "Other name"}),
        ({}, {"name": "INT-001 · different wording"}),
        ({"name": "Shared name"}, {"name": "Shared name"}),
    ], ids=["leanix id", "externalId", "INT code", "exact name"])
    def test_duplicates_merge_on_strongest_key(self, write_leanix, tmp_path, first, second):
        base = interface_row("INT-001 · Ledger → Billing", "Ledger", "Billing")
        write_leanix("apps.xlsx", [app_row("Billing"), app_row("Ledger")])
        write_leanix("a.xlsx", [{**base, **first}])
        write_leanix("b.xlsx", [{**base, **second}])
        assert len(run(tmp_path).architecture.connections) == 1

    def test_leanix_id_gives_stable_application_id(self, write_leanix):
        path = write_leanix("apps.xlsx", [app_row("Billing", id="48a56c32-8674-4624-bc5c-8e4f1d3c37c7")])
        first = run(path).architecture.applications[0]
        second = run(path).architecture.applications[0]
        assert first.source_system == "leanix"
        assert first.source_id == "48a56c32-8674-4624-bc5c-8e4f1d3c37c7"
        assert first.id == second.id
        assert first.id.startswith("APP-")

    def test_missing_leanix_id_generates_stable_id_and_reports_it(self, write_leanix):
        path = write_leanix("apps.xlsx", [app_row("Door Pricing Services")])
        first = run(path)
        assert first.architecture.applications[0].id == run(path).architecture.applications[0].id
        assert "generated_id" in codes(first, "info")

    def test_application_rows_merge_across_files(self, write_leanix, tmp_path):
        write_leanix("apps.xlsx", [app_row("Billing", id="b-1", businessCriticality="missionCritical")])
        write_leanix("06_Update_Applications.xlsx", [app_row("Billing", id="b-1", lxHostingType="saas")])
        app = run(tmp_path).architecture.applications[0]
        assert app.business_criticality == "High"
        assert app.hosting_type == "SaaS"


# Value mappings

class TestMappings:

    @pytest.mark.parametrize("leanix, ours", [
        ("missionCritical", "High"),
        ("businessCritical", "High"),
        ("businessOperational", "Medium"),
        ("administrativeService", "Low"),
    ])
    def test_business_criticality_maps_four_levels_to_three(self, write_leanix, leanix, ours):
        app = run(write_leanix("apps.xlsx", [app_row("A", businessCriticality=leanix)])).architecture.applications[0]
        assert app.business_criticality == ours
        assert app.extra_attributes == {"businessCriticality": leanix}

    @pytest.mark.parametrize("leanix, hosting, environment", [
        ("saas", "SaaS", "Cloud"),
        ("paas", "PaaS", "Cloud"),
        ("iaas", "IaaS", "Cloud"),
        ("onPremise", "On-Premise", "On-Premise"),
        ("hybrid", "Hybrid", "Hybrid"),
        ("desktopOrLaptop", "Desktop", "On-Premise"),
        ("mobile", "Mobile", None),
    ])
    def test_hosting_type_maps_to_deployment_environment(self, write_leanix, leanix, hosting, environment):
        app = run(write_leanix("apps.xlsx", [app_row("A", lxHostingType=leanix)])).architecture.applications[0]
        assert app.hosting_type == hosting
        assert app.deployment_environment == environment
        if environment:
            assert app.field_sources["deployment_environment"].detail == "derived from hosting_type"

    @pytest.mark.parametrize("leanix, ours", [
        ("synchronous", "API"),
        ("asynchronous", "Message Queue"),
        ("batch", "File Transfer"),
        (None, "Other"),
    ])
    def test_interface_type_maps_to_relationship(self, write_leanix, leanix, ours):
        row = interface_row("INT-001 · B → A", "B", "A")
        if leanix:
            row["interfaceType"] = leanix
        path = write_leanix("data.xlsx", [app_row("A"), app_row("B"), row])
        assert run(path).architecture.connections[0].relationship == ours

    def test_owner_comes_from_responsible_subscription(self, write_leanix):
        path = write_leanix("apps.xlsx", [app_row("A", **{"subscriptions:RESPONSIBLE": "demo.user@company.com"})])
        assert run(path).architecture.applications[0].owner == "demo.user@company.com"

    def test_unrecognized_value_is_kept_and_reported(self, write_leanix):
        result = run(write_leanix("apps.xlsx", [app_row("A", lxTimeClassification="Sunset")]))
        app = result.architecture.applications[0]
        assert app.time_classification is None
        assert app.extra_attributes == {"lxTimeClassification": "Sunset"}
        assert "unrecognized_value" in codes(result, "warning")

    def test_columns_without_a_model_field_go_to_extra_attributes(self, write_leanix):
        path = write_leanix("apps.xlsx", [app_row(
            "A", functionalSuitability="appropriate", relApplicationToBusinessCapability="HR;Finance"
        )])
        extra = run(path).architecture.applications[0].extra_attributes
        assert extra == {
            "functionalSuitability": "appropriate",
            "relApplicationToBusinessCapability": ["HR", "Finance"],
        }


# Interfaces -> connections

class TestConnections:

    def test_consumer_depends_on_provider(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("Snowflake"), app_row("Dynamics 365 OC CRM"),
            interface_row(
                "INT-010 · Snowflake → D365 · Customer Parent", "Snowflake", "Dynamics 365 OC CRM",
                relInterfaceToDataObject="Customer (Parent / SoldTo / ShipTo)",
            ),
        ])
        result = run(path)
        conn = result.architecture.connections[0]
        assert conn.source_application_id == app_by_name(result, "Dynamics 365 OC CRM").id
        assert conn.target_application_id == app_by_name(result, "Snowflake").id
        assert conn.interface_id == "INT-010"
        assert conn.data_objects == ["Customer (Parent / SoldTo / ShipTo)"]
        assert conn.direction == "unidirectional"

    def test_bidirectional_interface_is_marked(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("Snowflake"), app_row("Infor CPQ"),
            interface_row("INT-020 · Snowflake ↔ Infor CPQ · Customer SKU", "Snowflake", "Infor CPQ"),
        ])
        conns = run(path).architecture.connections
        assert len(conns) == 1
        assert conns[0].direction == "bidirectional"

    def test_data_flow_direction_column_wins_over_name(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("A"), app_row("B"),
            interface_row("INT-001 · B → A", "B", "A", dataFlowDirection="biDirectional"),
        ])
        assert run(path).architecture.connections[0].direction == "bidirectional"

    def test_several_interfaces_between_the_same_pair_stay_separate(self, write_leanix):
        rows = [app_row("Snowflake"), app_row("CRM")] + [
            interface_row(f"INT-01{n} · Snowflake → CRM", "Snowflake", "CRM") for n in (0, 1, 2)
        ]
        conns = run(write_leanix("data.xlsx", rows)).architecture.connections
        assert sorted(c.interface_id for c in conns) == ["INT-010", "INT-011", "INT-012"]

    def test_interface_with_one_side_missing_is_reported_not_connected(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("Infor CPQ"),
            interface_row("INT-006 · Unity Share → Infor CPQ · VMI Stock", None, "Infor CPQ"),
        ])
        result = run(path)
        assert result.architecture.connections == []
        assert result.report.incomplete_interfaces == ["INT-006"]
        message = next(i.message for i in result.report.issues if i.code == "incomplete_interface")
        assert "no provider" in message

    def test_planned_interface_keeps_lifecycle_status(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("A"), app_row("B"),
            interface_row("INT-027 · B → A", "B", "A", **{"lifecycle:plan": "2026-08-20"}),
        ])
        assert run(path).architecture.connections[0].lifecycle_status == "Plan"

    def test_future_dates_count_as_plan(self, write_leanix):
        path = write_leanix("apps.xlsx", [app_row("A", **{"lifecycle:active": "2027-01-01"})])
        assert run(path).architecture.applications[0].lifecycle_status == "Plan"

    def test_unknown_referenced_application_becomes_placeholder(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("CRM"),
            interface_row("INT-013 · CRM → mConnect · Contacts", "CRM", "mConnect"),
            interface_row("INT-014 · CRM → mConnect · Accounts", "CRM", "mConnect"),
        ])
        result = run(path)
        placeholder = app_by_name(result, "mConnect")
        assert placeholder.source_system == "placeholder"
        assert all(placeholder.field_sources[f].kind == "missing" for f in TRACKED_FIELDS if f != "data_objects")
        assert result.report.placeholder_applications == ["mConnect"]
        assert len(result.architecture.connections) == 2

    def test_name_matching_ignores_case_and_dash_variants(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("In-House Pricing"), app_row("CPQ"),
            interface_row("INT-001 · Pricing → CPQ", "in‑house pricing", "CPQ"),
        ])
        result = run(path)
        assert result.report.placeholder_applications == []
        assert len(result.architecture.connections) == 1

    def test_middleware_stays_on_connections_not_in_graph(self, write_leanix):
        rows = [app_row("A"), app_row("B"), app_row("C")] + [
            interface_row(f"INT-00{n} · {p} → {c}", p, c, relInterfaceToITComponent="Boomi SaaS Hosting")
            for n, (p, c) in enumerate([("A", "B"), ("B", "C")], start=1)
        ]
        result = run(write_leanix("data.xlsx", rows))
        assert {a.name for a in result.architecture.applications} == {"A", "B", "C"}
        assert all(c.via == ["Boomi SaaS Hosting"] for c in result.architecture.connections)

    def test_it_components_attach_to_their_applications(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("Pricing"),
            {"type": "ITComponent", "name": "Pricing API tier", "relITComponentToApplication": "Pricing"},
            {"type": "ITComponent", "name": "Orphan", "relITComponentToApplication": "Nowhere"},
        ])
        result = run(path)
        assert result.architecture.applications[0].it_components == ["Pricing API tier"]
        assert "unknown_component_application" in codes(result, "warning")

    def test_data_objects_are_derived_from_interfaces(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("A"), app_row("B"),
            interface_row("INT-001 · B → A", "B", "A", relInterfaceToDataObject="Customer;Price"),
        ])
        app = app_by_name(run(path), "A")
        assert app.data_objects == ["Customer", "Price"]
        assert app.field_sources["data_objects"].detail == "derived from interface data objects"


# Missing data and provenance

class TestMissingDataAndProvenance:

    def test_missing_fields_are_left_empty_not_guessed(self, write_leanix):
        app = run(write_leanix("apps.xlsx", [app_row("Billing")])).architecture.applications[0]
        for field_name in TRACKED_FIELDS:
            assert app.field_sources[field_name].kind == "missing"
        assert app.data_sensitivity is None
        assert app.business_criticality is None

    def test_imported_field_records_its_source_cell(self, write_leanix):
        app = run(write_leanix("apps.xlsx", [app_row("A", businessCriticality="missionCritical")])).architecture.applications[0]
        source = app.field_sources["business_criticality"]
        assert source.kind == "imported"
        assert source.system == "leanix"
        assert source.detail == "apps.xlsx#Export 2026-01-01!R3:businessCriticality"

    def test_report_lists_missing_data_and_coverage(self, write_leanix):
        result = run(write_leanix("apps.xlsx", [
            app_row("A", businessCriticality="missionCritical"), app_row("B"),
        ]))
        report = result.report
        assert report.field_coverage["business_criticality"] == 1
        assert report.field_coverage["network_protocols"] == 0
        missing_a = next(m for m in report.missing_by_application if m.application_name == "A")
        assert "business_criticality" not in missing_a.missing_fields
        assert "network_protocols" in missing_a.missing_fields

    def test_crypto_fields_are_never_filled_from_other_data(self, write_leanix):
        path = write_leanix("data.xlsx", [
            app_row("Identity", lxHostingType="saas"), app_row("Portal"),
            interface_row("INT-025 · Identity → Portal", "Identity", "Portal", relInterfaceToDataObject="Identity / User"),
        ])
        app = app_by_name(run(path), "Identity")
        for field_name in CRYPTO_FIELDS:
            assert getattr(app, field_name) is None
            assert app.field_sources[field_name].kind == "missing"
