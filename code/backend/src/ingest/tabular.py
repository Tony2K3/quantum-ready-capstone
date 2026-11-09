"""
Low-level helpers for reading spreadsheet-like files and cleaning cell values.

Shared by the LeanIX and native CSV adapters. Nothing here knows about the
Pydantic models.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import openpyxl

TABLE_SUFFIXES = (".xlsx", ".xlsm", ".csv")

# Excel stores dates as days since 1899-12-30 (accounting for the 1900 leap-year bug).
_EXCEL_EPOCH = date(1899, 12, 30)
_MAX_EXCEL_SERIAL = 2958465  # 9999-12-31

_DASHES = {ord(c): "-" for c in "‐‑‒–—―−"}


@dataclass
class Sheet:
    """One sheet (or one CSV file) as a header plus numbered data rows."""

    name: str | None
    header: list[str]
    # (spreadsheet row number, {column key: raw cell value})
    rows: list[tuple[int, dict[str, Any]]]


def read_table_file(path: Path) -> list[Sheet]:
    """Read an .xlsx/.xlsm workbook or a .csv file into sheets."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as fh:
            return [_rows_to_sheet(None, csv.reader(fh))]
    if suffix in (".xlsx", ".xlsm"):
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            return [
                _rows_to_sheet(ws.title, ws.iter_rows(values_only=True))
                for ws in workbook.worksheets
            ]
        finally:
            workbook.close()
    raise ValueError(f"Unsupported file type '{path.suffix}'")


def _rows_to_sheet(name: str | None, raw_rows: Iterable[Sequence[Any]]) -> Sheet:
    rows_iter = iter(raw_rows)
    header_row = next(rows_iter, None)
    if header_row is None:
        return Sheet(name=name, header=[], rows=[])
    header = [str(h).strip() if h is not None else "" for h in header_row]
    rows: list[tuple[int, dict[str, Any]]] = []
    for row_number, raw in enumerate(rows_iter, start=2):
        record = {col: value for col, value in zip(header, raw, strict=False) if col}
        if any(as_text(v) is not None for v in record.values()):
            rows.append((row_number, record))
    return Sheet(name=name, header=header, rows=rows)


def expand_paths(paths: Iterable[str | Path], suffixes: Sequence[str] = TABLE_SUFFIXES) -> list[Path]:
    """
    Expand files and folders into a de-duplicated list of files.

    Folders are read non-recursively. Office lock files (~$...) and hidden
    files are ignored.
    """
    result: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            candidates = sorted(
                p for p in path.iterdir()
                if p.is_file()
                and p.suffix.lower() in suffixes
                and not p.name.startswith(("~$", "."))
            )
        elif path.is_file():
            candidates = [path]
        else:
            raise FileNotFoundError(f"No such file or folder: {path}")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                result.append(candidate)
    return result


# Cell value cleaning

def as_text(value: Any) -> str | None:
    """Convert a raw cell value to stripped text, or None when empty."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def split_list(value: Any) -> list[str]:
    """Split a semicolon-separated cell into a list of non-empty values."""
    text = as_text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def parse_date(value: Any) -> date:
    """
    Parse an Excel serial number, a date/datetime cell, or an ISO date string.

    Raises ValueError for anything else.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return _from_excel_serial(float(value))
    text = as_text(value)
    if text is None:
        raise ValueError("empty date")
    if re.fullmatch(r"\d{1,7}(\.\d+)?", text):
        return _from_excel_serial(float(text))
    return date.fromisoformat(text[:10])


def _from_excel_serial(serial: float) -> date:
    if not 1 <= serial <= _MAX_EXCEL_SERIAL:
        raise ValueError(f"Excel date serial out of range: {serial}")
    return _EXCEL_EPOCH + timedelta(days=int(serial))


def norm_key(text: str) -> str:
    """Normalise a name for matching: Unicode-fold, unify dashes, casefold, collapse spaces."""
    folded = unicodedata.normalize("NFKC", text).translate(_DASHES)
    return " ".join(folded.casefold().split())
