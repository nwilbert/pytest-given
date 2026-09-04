"""The ``pytest-given`` console script.

An entry point like the ``plugin`` package: allowed to import from any
subpackage, and holding nothing those subpackages could hold. Owns the argparse
root; every subcommand registers its own parser and binds its handler with
``set_defaults``, so dispatch stays one call.

The subcommands live beside this module rather than inside the packages they
drive — ``report/`` renders, and knows nothing about argv, exit codes or
stderr.
"""

import argparse
from collections.abc import Callable

from .report import add_report_parser
from .skills import add_skills_parser

__all__ = ['main']


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='pytest-given',
        description='pytest-given command-line tools.',
    )
    subparsers = parser.add_subparsers(required=True)
    add_report_parser(subparsers)
    add_skills_parser(subparsers)
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)
