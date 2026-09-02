"""Command-line entry point for the ``pytest-given`` console script.

Top-level orchestrator like the ``plugin`` package: allowed to import from any
subpackage. Owns the argparse root; every subcommand registers its own parser
and binds its handler with ``set_defaults``, so dispatch stays one call.
"""

import argparse
import sys
from collections.abc import Callable
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath

from .report import add_report_parser

type SkillTree = dict[PurePosixPath, bytes]

DEFAULT_SKILLS_DEST = Path('.claude') / 'skills'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='pytest-given',
        description='pytest-given command-line tools.',
    )
    subparsers = parser.add_subparsers(required=True)
    add_report_parser(subparsers)
    _add_skills_parser(subparsers)
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


def _install_skills(dest: Path) -> int:
    """Mirror the bundled skill directories into ``dest``.

    Touches only the bundled ``pytest-given-*`` directories: sibling skills in
    ``dest`` are never read or written.
    """
    bundled = _bundled_skill_tree()
    stale = _stale_files(dest, bundled)
    for rel, data in bundled.items():
        target = dest.joinpath(*rel.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f'wrote {target}')
    for path in stale:
        path.unlink()
        print(f'removed stale {path}')
    return 0


def _check_skills(dest: Path) -> int:
    bundled = _bundled_skill_tree()
    return _report_drift(dest, bundled, _stale_files(dest, bundled))


def _run_skills_install(args: argparse.Namespace) -> int:
    dest: Path = args.dest
    try:
        return _check_skills(dest) if args.check else _install_skills(dest)
    except OSError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


def _add_skills_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    skills_parser = subparsers.add_parser(
        'skills', help='Manage the bundled agent skills'
    )
    skills_subparsers = skills_parser.add_subparsers(required=True)
    install_parser = skills_subparsers.add_parser(
        'install', help='Install the bundled agent skills into a project'
    )
    install_parser.set_defaults(handler=_run_skills_install)
    install_parser.add_argument(
        '--dest',
        type=Path,
        default=DEFAULT_SKILLS_DEST,
        help='Skills directory to install into (default: .claude/skills)',
    )
    install_parser.add_argument(
        '--check',
        action='store_true',
        help='Report drift against the bundled skills instead of writing.',
    )


def _report_drift(dest: Path, bundled: SkillTree, stale: list[Path]) -> int:
    findings: list[str] = []
    for rel, data in bundled.items():
        target = dest.joinpath(*rel.parts)
        if not target.is_file():
            findings.append(f'missing: {target}')
        elif target.read_bytes() != data:
            findings.append(f'differs: {target}')
    findings.extend(f'stale: {path}' for path in stale)
    for finding in findings:
        print(finding)
    if findings:
        return 1
    print(f'skills in sync: {dest}')
    return 0


def _bundled_skill_tree() -> SkillTree:
    tree: SkillTree = {}
    _collect(files('pytest_given') / 'skills_data', PurePosixPath(), tree)
    return tree


def _collect(node: Traversable, prefix: PurePosixPath, tree: SkillTree) -> None:
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        if child.is_dir():
            _collect(child, prefix / child.name, tree)
        else:
            tree[prefix / child.name] = child.read_bytes()


def _stale_files(dest: Path, bundled: SkillTree) -> list[Path]:
    owned_dirs = {rel.parts[0] for rel in bundled}
    known = {dest.joinpath(*rel.parts) for rel in bundled}
    return [
        path
        for name in sorted(owned_dirs)
        if (dest / name).is_dir()
        for path in sorted((dest / name).rglob('*'))
        if path.is_file() and path not in known
    ]


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
