"""Arguments more than one subcommand declares, so that each reads the same."""

import argparse
from pathlib import Path

from ..report import DEFAULT_JSON_PATH

JSON_REPORT_DEFAULT_HELP = (
    f'(default: {DEFAULT_JSON_PATH.as_posix()}, where a bare --given-json writes it)'
)


def add_json_report_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        'json_file',
        nargs='?',
        type=Path,
        default=DEFAULT_JSON_PATH,
        help=f'Path to JSON report data {JSON_REPORT_DEFAULT_HELP}',
    )
