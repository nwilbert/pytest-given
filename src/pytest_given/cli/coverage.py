"""The `pytest-given coverage` subcommand: print a JSON report's story coverage."""

import argparse
import json
import sys
from pathlib import Path

from ..model import PytestGivenError, read_report
from ..report import build_coverage_records
from .arguments import add_json_report_argument


def add_coverage_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    coverage_parser = subparsers.add_parser(
        'coverage',
        help='Print which scenarios cover each story sentence, as JSON',
    )
    coverage_parser.set_defaults(handler=run_coverage)
    add_json_report_argument(coverage_parser)


def run_coverage(args: argparse.Namespace) -> int:
    json_file: Path = args.json_file
    try:
        report = read_report(json_file)
    except (PytestGivenError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    records = build_coverage_records(report)
    print(json.dumps(records, indent=2))
    uncovered = sum(
        1 for record in records if record['tracked'] and not record['scenario_ids']
    )
    if not uncovered:
        return 0
    sentences = 'sentence has' if uncovered == 1 else 'sentences have'
    print(f'{uncovered} tracked {sentences} no scenario.', file=sys.stderr)
    return 1
