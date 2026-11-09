"""
Shared fixtures: build synthetic LeanIX-style workbooks and native CSVs.

All data here is made up. Real client exports must not be used in tests.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import openpyxl
import pytest

LeanixWriter = Callable[..., Path]
CsvWriter = Callable[[str, Sequence[str], Sequence[Sequence[Any]]], Path]


@pytest.fixture
def write_leanix(tmp_path: Path) -> LeanixWriter:
    """
    Write a LeanIX-style workbook: key row, optional label row, data rows,
    plus a ReadMe sheet. Rows are dicts keyed by LeanIX column key.
    """

    def _write(
        file_name: str,
        rows: Sequence[dict[str, Any]],
        label_row: bool = True,
        readme: bool = True,
        folder: Path | None = None,
    ) -> Path:
        header: list[str] = []
        for row in rows:
            for key in row:
                if key not in header:
                    header.append(key)
        for required in ("id", "type", "name"):
            if required not in header:
                header.insert(0, required)

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Export 2026-01-01"
        sheet.append(header)
        if label_row:
            sheet.append(["ID" if k == "id" else "Type" if k == "type" else k for k in header])
        for row in rows:
            sheet.append([row.get(key) for key in header])
        if readme:
            notes = workbook.create_sheet("ReadMe")
            notes.append(["LeanIX inventory export"])
            notes.append(["type", "Application"])
        target = (folder or tmp_path) / file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(target)
        return target

    return _write


@pytest.fixture
def write_csv(tmp_path: Path) -> CsvWriter:
    def _write(file_name: str, header: Sequence[str], rows: Sequence[Sequence[Any]]) -> Path:
        target = tmp_path / file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)
        return target

    return _write
