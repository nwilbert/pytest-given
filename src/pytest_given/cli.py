import argparse
import sys
from pathlib import Path

from pytest_given.renderer import render_html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='pytest-given',
        description='Generate HTML reports from pytest-given JSON data.',
    )
    subparsers = parser.add_subparsers(dest='command')

    report_parser = subparsers.add_parser(
        'report', help='Generate HTML report from JSON data'
    )
    report_parser.add_argument('json_file', type=Path, help='Path to JSON report data')
    report_parser.add_argument(
        '-o',
        '--output',
        type=Path,
        default=Path('given-report/report.html'),
        help='Output HTML file path (default: given-report/report.html)',
    )

    args = parser.parse_args(argv)

    if args.command == 'report':
        if not args.json_file.exists():
            print(f'Error: {args.json_file} not found', file=sys.stderr)
            return 1
        render_html(args.json_file, args.output)
        print(f'Report generated: {args.output}')
        return 0

    parser.print_help()
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
