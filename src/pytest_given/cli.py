"""Command-line entry point for the ``pytest-given`` console script.

Top-level orchestrator like ``plugin.py``: allowed to import from any
subpackage. Owns the argparse root; subcommands register themselves here.
"""

import argparse
import sys

from .report.cli import add_report_parser, run_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='pytest-given',
        description='pytest-given command-line tools.',
    )
    subparsers = parser.add_subparsers(dest='command')
    add_report_parser(subparsers)
    args = parser.parse_args(argv)
    if args.command == 'report':
        return run_report(args)
    parser.print_help()
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
