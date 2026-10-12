"""Peter's Application schema, as returned by the fetch_applications tool."""

from connectors import tools
from connectors.applications import most_sensitive
from connectors.schema import APPLICATION_FIELDS


async def test_fetch_applications_uses_peters_fields_in_order():
    result = await tools.fetch_applications()
    assert result["count"] == 7
    for app in result["applications"]:
        assert tuple(app) == APPLICATION_FIELDS


async def test_application_fields_derived_from_connections():
    apps = {a["name"]: a for a in (await tools.fetch_applications())["applications"]}

    payroll = apps["Legacy Payroll"]
    assert payroll["data_sensitivity"] == "restricted"  # most sensitive of its two data objects
    assert "Payroll Run: 10 years" in payroll["data_longevity"]
    assert payroll["tech_stack"] == "IBM z/OS 2.4"
    assert "IBM" in payroll["vendor_dependency"]  # vendor of its tech stack
    assert payroll["network_protocols"] == "SFTP"

    idp = apps["Identity Provider"]
    assert idp["network_protocols"] == "SAML over HTTPS"  # from the interface it provides
    assert idp["deployment_environment"] == "On-premises"


async def test_crypto_columns_empty_in_output():
    for app in (await tools.fetch_applications())["applications"]:
        for f in ("cryptography", "pqc_readiness", "crypto_agility", "key_management_type"):
            assert app[f] == ""


def test_most_sensitive_picks_highest_rank():
    assert most_sensitive(["Public", "Restricted", "Internal"]) == "Restricted"
    assert most_sensitive([]) == ""
