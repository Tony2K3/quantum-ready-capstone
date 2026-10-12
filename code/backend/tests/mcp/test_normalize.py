from connectors import config
from connectors.normalize import normalize_attributes


def test_aliases_map_to_standard_attributes():
    attrs = normalize_attributes({
        "Business Criticality": "High", "Application Owner": "Team A", "EOL": "2027-01-01",
        "Hosting Type": "AWS", "Department": "Finance", "Data Retention": "7 years",
        "Cost Center": "CC-12",
    })
    assert attrs["criticality"] == "High"
    assert attrs["owner"] == "Team A"
    assert attrs["end_of_life"] == "2027-01-01"
    assert attrs["hosting"] == "AWS"
    assert attrs["business_unit"] == "Finance"
    assert attrs["retention"] == "7 years"
    assert attrs["other_properties"] == {"Cost Center": "CC-12"}


def test_crypto_fields_are_dropped_while_flag_is_off():
    attrs = normalize_attributes({
        "Encryption": "RSA-2048", "Key Management": "HSM", "PQC Readiness": "Low",
        "Certificate Expiry": "2026-12-01", "Owner": "Team A",
    })
    assert attrs["cryptography"] == ""
    assert attrs["key_management_type"] == ""
    assert attrs["pqc_readiness"] == ""
    assert attrs["other_properties"] == {}
    assert attrs["owner"] == "Team A"


def test_crypto_fields_come_back_when_flag_is_on(monkeypatch):
    monkeypatch.setattr(config, "INCLUDE_CRYPTO_FIELDS", True)
    attrs = normalize_attributes({"Encryption": "RSA-2048", "Key Management": "HSM"})
    assert attrs["cryptography"] == "RSA-2048"
    assert attrs["key_management_type"] == "HSM"
