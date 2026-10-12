import csv
import os

from connectors import tools
from connectors.schema import APPLICATION_FIELDS


async def test_export_writes_every_file_with_headers(tmp_path):
    result = await tools.export_csv(str(tmp_path))
    expected = {
        "applications.csv", "dependencies.csv", "data_objects.csv", "interfaces.csv",
        "it_components.csv", "business_capabilities.csv", "relationships.csv",
    }
    assert set(result["files"]) == expected
    for name in expected:
        with open(tmp_path / name, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == result["files"][name]["rows"]
        assert rows, f"{name} is empty"


async def test_applications_csv_starts_with_peters_columns(tmp_path):
    await tools.export_csv(str(tmp_path))
    with open(tmp_path / "applications.csv", newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert tuple(header[: len(APPLICATION_FIELDS)]) == APPLICATION_FIELDS


async def test_no_crypto_values_anywhere_in_export(tmp_path):
    await tools.export_csv(str(tmp_path))
    for name in os.listdir(tmp_path):
        text = (tmp_path / name).read_text(encoding="utf-8").lower()
        for word in ("rsa", "ecdsa", "aes-", "encrypt"):
            assert word not in text, f"{word!r} found in {name}"
