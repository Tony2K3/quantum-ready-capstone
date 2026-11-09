"""
Tests for the native CSV adapter, CSV overlays on LeanIX data, the CLI,
and keeping descriptions out of the LLM prompt.
"""

from __future__ import annotations

import json
from datetime import date

from src.ingest import normalize, write_templates
from src.ingest.cli import main
from src.ingest.csv_native import APPLICATION_COLUMNS, CONNECTION_COLUMNS
from src.roadmap.llm.context import assemble_prompt
from src.roadmap.models.priority import ApplicationPriority

AS_OF = date(2026, 11, 8)
APP_HEADER = ["id", "name", "description", "data_sensitivity", "network_protocols", "crypto_agility"]


class TestNativeCsv:

    def test_imports_applications_and_connections(self, write_csv, tmp_path):
        write_csv("applications.csv", APP_HEADER, [
            ["APP-1", "Payments", "", "High", "TLS 1.2;SSH 2", "false"],
            ["APP-2", "Portal", "", "", "", ""],
        ])
        write_csv("connections.csv", ["source_application_id", "target_application_id", "relationship", "via"], [
            ["APP-2", "APP-1", "API", "Gateway"],
        ])
        result = normalize([("csv", [tmp_path])], as_of=AS_OF)
        payments = result.architecture.applications[0]
        assert payments.id == "APP-1"
        assert payments.network_protocols == ["TLS 1.2", "SSH 2"]
        assert payments.crypto_agility is False
        assert payments.field_sources["data_sensitivity"].kind == "imported"
        assert payments.field_sources["data_sensitivity"].system == "csv"
        conn = result.architecture.connections[0]
        assert (conn.source_application_id, conn.target_application_id) == ("APP-2", "APP-1")
        assert conn.via == ["Gateway"]

    def test_connections_may_reference_applications_by_name(self, write_csv, tmp_path):
        write_csv("applications.csv", ["id", "name"], [["APP-1", "Payments"], ["APP-2", "Portal"]])
        write_csv("connections.csv", ["source_application_id", "target_application_id", "relationship"], [
            ["Portal", "Payments", "API"],
        ])
        conn = normalize([("csv", [tmp_path])], as_of=AS_OF).architecture.connections[0]
        assert (conn.source_application_id, conn.target_application_id) == ("APP-2", "APP-1")

    def test_unknown_application_in_csv_connection_is_an_error(self, write_csv, tmp_path):
        write_csv("applications.csv", ["id", "name"], [["APP-1", "Payments"]])
        write_csv("connections.csv", ["source_application_id", "target_application_id", "relationship"], [
            ["APP-404", "APP-1", "API"],
        ])
        result = normalize([("csv", [tmp_path])], as_of=AS_OF)
        assert result.architecture.connections == []
        assert result.report.placeholder_applications == []
        assert any(i.code == "unknown_application" for i in result.report.issues)

    def test_invalid_value_is_reported_by_location_and_other_rows_survive(self, write_csv, tmp_path):
        secret = "Internal note about the ledger network layout"
        write_csv("applications.csv", APP_HEADER, [
            ["APP-1", "Payments", secret, "Very High", "", ""],
            ["APP-2", "Portal", "", "Low", "", ""],
        ])
        result = normalize([("csv", [tmp_path])], as_of=AS_OF)
        payments, portal = result.architecture.applications
        assert payments.data_sensitivity is None
        assert payments.field_sources["data_sensitivity"].kind == "missing"
        assert portal.data_sensitivity == "Low"
        issue = next(i for i in result.report.issues if i.code == "invalid_value")
        assert (issue.file, issue.row, issue.column) == ("applications.csv", 2, "data_sensitivity")
        assert "'Very High'" in issue.message and "'Low', 'Medium' or 'High'" in issue.message
        assert all(secret not in i.message for i in result.report.issues)

    def test_rows_without_id_or_name_are_skipped(self, write_csv, tmp_path):
        write_csv("applications.csv", ["id", "name"], [["", "Nameless id"], ["APP-2", "Portal"]])
        result = normalize([("csv", [tmp_path])], as_of=AS_OF)
        assert [a.id for a in result.architecture.applications] == ["APP-2"]
        assert any(i.code == "missing_required" for i in result.report.issues)

    def test_unknown_columns_are_kept_and_reported(self, write_csv, tmp_path):
        write_csv("applications.csv", ["id", "name", "cost_center"], [["APP-1", "Payments", "CC-12"]])
        result = normalize([("csv", [tmp_path])], as_of=AS_OF)
        assert result.architecture.applications[0].extra_attributes == {"cost_center": "CC-12"}
        assert any(i.code == "unknown_column" for i in result.report.issues)

    def test_templates_have_header_rows_only(self, tmp_path):
        apps, conns = write_templates(tmp_path / "templates")
        assert apps.read_text().strip().split(",") == list(APPLICATION_COLUMNS)
        assert conns.read_text().strip().split(",") == list(CONNECTION_COLUMNS)


class TestCsvOverlay:

    def test_csv_adds_fields_to_leanix_applications(self, write_leanix, write_csv, tmp_path):
        leanix_dir = tmp_path / "leanix"
        write_leanix("apps.xlsx", [
            {"type": "Application", "name": "Snowflake", "id": "sf-1", "lxHostingType": "saas"},
        ], folder=leanix_dir)
        first = normalize([("leanix", [leanix_dir])], as_of=AS_OF)
        snowflake_id = first.architecture.applications[0].id

        overlay = write_csv("overlay/applications.csv", ["id", "name", "network_protocols"], [
            [snowflake_id, "Snowflake", "TLS 1.2"],
        ])
        result = normalize([("leanix", [leanix_dir]), ("csv", [overlay])], as_of=AS_OF)
        app = result.architecture.applications[0]
        assert len(result.architecture.applications) == 1
        assert app.hosting_type == "SaaS"
        assert app.field_sources["hosting_type"].system == "leanix"
        assert app.network_protocols == ["TLS 1.2"]
        assert app.field_sources["network_protocols"].system == "csv"


class TestCli:

    def test_writes_architecture_and_report(self, write_leanix, tmp_path, capsys):
        write_leanix("data/apps.xlsx", [
            {"type": "Application", "name": "A"},
            {"type": "Application", "name": "B"},
            {"type": "Interface", "name": "INT-001 · B → A",
             "relInterfaceToProviderApplication": "B", "relInterfaceToConsumerApplication": "A"},
        ])
        out, report = tmp_path / "architecture.json", tmp_path / "report.json"
        code = main(["leanix", str(tmp_path / "data"), "--out", str(out), "--report", str(report),
                     "--as-of", "2026-11-08"])
        assert code == 0
        assert len(json.loads(out.read_text())["applications"]) == 2
        assert json.loads(report.read_text())["connection_count"] == 1
        assert "Applications: 2" in capsys.readouterr().err

    def test_exits_1_when_no_architecture_can_be_built(self, write_leanix, tmp_path):
        path = write_leanix("caps.xlsx", [{"type": "BusinessCapability", "name": "Order to cash"}])
        assert main(["leanix", str(path), "--out", str(tmp_path / "out.json")]) == 1
        assert not (tmp_path / "out.json").exists()

    def test_bluedolphin_is_not_supported_yet(self, tmp_path, capsys):
        assert main(["bluedolphin", str(tmp_path)]) == 2
        assert "not implemented" in capsys.readouterr().err

    def test_missing_path_exits_2(self, tmp_path):
        assert main(["leanix", str(tmp_path / "nope")]) == 2

    def test_template_command(self, tmp_path):
        assert main(["template", str(tmp_path / "t")]) == 0
        assert (tmp_path / "t" / "applications.csv").exists()


def test_descriptions_are_not_sent_to_the_llm(write_csv, tmp_path):
    secret = "Hosted in the Tampa data center behind an unauthenticated gateway"
    write_csv("applications.csv", ["id", "name", "description"], [["APP-1", "Payments", secret]])
    architecture = normalize([("csv", [tmp_path])], as_of=AS_OF).architecture
    priority = ApplicationPriority(
        application_id="APP-1", application_name="Payments",
        priority_level="High", priority_score=60.0, key_factors=[],
    )
    payload = assemble_prompt([priority], architecture, persona="CISO")
    assert secret not in payload.system_prompt
    assert secret not in payload.user_message
