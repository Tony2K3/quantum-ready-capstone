"""
Data normalizer: EA tool exports and CSVs -> validated EnterpriseArchitecture.

Typical use:

    from src.ingest import normalize

    result = normalize([("leanix", ["EAM Files/"]), ("csv", ["overrides/"])])
    result.architecture   # EnterpriseArchitecture, ready for generate_roadmap()
    result.report         # NormalizationReport: files, issues, missing data

Sources are applied in order; later sources override non-empty values from
earlier ones.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path

from .assemble import assemble
from .bluedolphin import BlueDolphinNotSupportedError, load_bluedolphin
from .csv_native import load_native_csv, write_templates
from .leanix import load_leanix
from .records import RawBundle
from .report import NormalizationError, NormalizationReport, NormalizationResult

SOURCE_TYPES = ("leanix", "csv", "bluedolphin")


def load(source_type: str, paths: Iterable[str | Path], include_templates: bool = False) -> RawBundle:
    """Run one adapter."""
    if source_type == "leanix":
        return load_leanix(paths, include_templates=include_templates)
    if source_type == "csv":
        return load_native_csv(paths)
    if source_type == "bluedolphin":
        return load_bluedolphin(paths)
    raise ValueError(f"Unknown source type '{source_type}'. Expected one of: {', '.join(SOURCE_TYPES)}.")


def normalize(
    sources: Sequence[tuple[str, Iterable[str | Path]]],
    as_of: date | None = None,
    include_templates: bool = False,
) -> NormalizationResult:
    """
    Import one or more sources and return a validated architecture plus report.

    Args:
        sources:           (source_type, paths) pairs, applied in order.
        as_of:             Date used to derive lifecycle status. Defaults to today.
        include_templates: Import LeanIX files named '*Template*' (skipped by default).

    Raises:
        NormalizationError: if no valid architecture can be produced.
        BlueDolphinNotSupportedError: for 'bluedolphin' sources, temp.
    """
    bundles = [load(kind, paths, include_templates) for kind, paths in sources]
    return assemble(bundles, as_of=as_of)


__all__ = [
    "SOURCE_TYPES",
    "BlueDolphinNotSupportedError",
    "NormalizationError",
    "NormalizationReport",
    "NormalizationResult",
    "assemble",
    "load",
    "load_bluedolphin",
    "load_leanix",
    "load_native_csv",
    "normalize",
    "write_templates",
]
