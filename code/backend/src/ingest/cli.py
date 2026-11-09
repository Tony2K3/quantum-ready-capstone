"""
Command-line interface for the normalizer: development and demo use only.

Examples:
    python -m src.ingest leanix "EAM Files/" --out architecture.json --report report.json
    python -m src.ingest leanix "EAM Files/" --overlay-csv filled_in/ --out architecture.json
    python -m src.ingest csv my_csvs/ --out architecture.json
    python -m src.ingest template templates/

Exit status: 0 on success (warnings allowed), 1 when no valid architecture
could be produced, 2 for usage errors or unsupported sources.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from . import (
    BlueDolphinNotSupportedError,
    NormalizationError,
    normalize,
    write_templates,
)
from .report import NormalizationReport


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingest",
        description="Normalize EA exports into an EnterpriseArchitecture JSON file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_import_options(p: argparse.ArgumentParser) -> None:
        p.add_argument("paths", nargs="+", help="Files and/or folders to import.")
        p.add_argument("--out", help="Write the architecture JSON here (default: stdout).")
        p.add_argument("--report", help="Write the normalization report JSON here.")
        p.add_argument(
            "--as-of", type=date.fromisoformat,
            help="Date for deriving lifecycle status (YYYY-MM-DD, default: today).",
        )

    leanix = sub.add_parser("leanix", help="Import LeanIX Excel/CSV exports.")
    add_import_options(leanix)
    leanix.add_argument(
        "--overlay-csv", action="append", default=[], metavar="PATH",
        help="Native CSV files/folders applied on top of the LeanIX data (repeatable).",
    )
    leanix.add_argument(
        "--include-templates", action="store_true",
        help="Also import files named '*Template*' (skipped by default).",
    )

    csv_parser = sub.add_parser("csv", help="Import native applications/connections CSVs.")
    add_import_options(csv_parser)

    bluedolphin = sub.add_parser("bluedolphin", help="Import BlueDolphin exports (not yet supported).")
    add_import_options(bluedolphin)

    template = sub.add_parser("template", help="Write blank native CSV templates.")
    template.add_argument("directory", help="Folder to write applications.csv and connections.csv into.")
    return parser


def _summary(report: NormalizationReport) -> str:
    lines = [
        (
            f"Applications: {report.application_count} "
            f"({len(report.placeholder_applications)} placeholders)"
        ),
        (
            f"Connections:  {report.connection_count} "
            f"({len(report.incomplete_interfaces)} incomplete interfaces skipped)"
        ),
        (
            f"Files:        {sum(f.status == 'imported' for f in report.files)} imported, "
            f"{sum(f.status == 'skipped' for f in report.files)} skipped, "
            f"{sum(f.status == 'error' for f in report.files)} unreadable"
        ),
        (
            f"Issues:       {report.count('error')} errors, "
            f"{report.count('warning')} warnings, {report.count('info')} info"
        ),
    ]
    errors = [i for i in report.issues if i.severity == "error"]
    for issue in errors[:10]:
        where = f" [{issue.file}{f' row {issue.row}' if issue.row else ''}]" if issue.file else ""
        lines.append(f"  error: {issue.message}{where}")
    if len(errors) > 10:
        lines.append(f"  ... and {len(errors) - 10} more errors (see the report)")
    return "\n".join(lines)


def _write(path: str | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text + "\n")
    else:
        Path(path).write_text(text + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "template":
        for path in write_templates(args.directory):
            print(f"Wrote {path}", file=sys.stderr)
        return 0

    sources: list[tuple[str, list[str]]] = [(args.command, args.paths)]
    if args.command == "leanix":
        sources += [("csv", [p]) for p in args.overlay_csv]

    try:
        result = normalize(
            sources,
            as_of=args.as_of,
            include_templates=getattr(args, "include_templates", False),
        )
    except BlueDolphinNotSupportedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except NormalizationError as exc:
        print(f"Normalization failed: {exc}", file=sys.stderr)
        print(_summary(exc.report), file=sys.stderr)
        if args.report:
            _write(args.report, exc.report.model_dump_json(indent=2))
        return 1

    _write(args.out, result.architecture.model_dump_json(indent=2, exclude_none=True))
    if args.report:
        _write(args.report, result.report.model_dump_json(indent=2))
    print(_summary(result.report), file=sys.stderr)
    return 0
