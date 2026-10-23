"""The ``pytest-given skills`` subcommand: mirror the bundled skills into a
project's ``.claude/skills/``, or report drift against them."""

import argparse
import sys
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath

type SkillTree = dict[PurePosixPath, bytes]

DEFAULT_SKILLS_DEST = Path('.claude') / 'skills'
# The layout `library-skills` scans for: `.agents/skills/<name>/SKILL.md`.
BUNDLED_SKILLS_ROOT = files('pytest_given') / '.agents' / 'skills'


def add_skills_parser(
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


def _run_skills_install(args: argparse.Namespace) -> int:
    dest: Path = args.dest
    try:
        return _report_drift(dest) if args.check else _install_skills(dest)
    except OSError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


def _install_skills(dest: Path) -> int:
    """Mirror the bundled skill directories into ``dest``.

    Touches only the bundled ``pytest-given-*`` directories: sibling skills in
    ``dest`` are never read or written.
    """
    bundled = _bundled_skill_tree()
    stale, stale_dirs = _stale(dest, bundled)
    for rel, data in bundled.items():
        target = dest.joinpath(*rel.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f'wrote {target}')
    for path in stale:
        path.unlink()
        print(f'removed stale {path}')
    for path in stale_dirs:
        path.rmdir()
        print(f'removed stale directory {path}')
    return 0


def _report_drift(dest: Path) -> int:
    """Report how ``dest`` differs from the bundled skills, without writing."""
    bundled = _bundled_skill_tree()
    findings: list[str] = []
    for rel, data in bundled.items():
        target = dest.joinpath(*rel.parts)
        if not target.is_file():
            findings.append(f'missing: {target}')
        elif target.read_bytes() != data:
            findings.append(f'differs: {target}')
    stale, stale_dirs = _stale(dest, bundled)
    findings.extend(f'stale: {path}' for path in stale)
    findings.extend(f'stale: {path} (directory)' for path in stale_dirs)
    for finding in findings:
        print(finding)
    if findings:
        return 1
    print(f'skills in sync: {dest}')
    return 0


def _bundled_skill_tree() -> SkillTree:
    tree: SkillTree = {}
    _collect(BUNDLED_SKILLS_ROOT, PurePosixPath(), tree)
    return tree


def _collect(node: Traversable, prefix: PurePosixPath, tree: SkillTree) -> None:
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        if child.is_dir():
            _collect(child, prefix / child.name, tree)
        else:
            tree[prefix / child.name] = child.read_bytes()


def _stale(dest: Path, bundled: SkillTree) -> tuple[list[Path], list[Path]]:
    """What no bundled file accounts for under the bundled skills' directories:
    the entries to unlink, a symlink among them whatever it points at, then
    the directories left to prune, each before its parent."""
    known = {dest.joinpath(*rel.parts) for rel in bundled}
    needed = {
        dest.joinpath(*rel.parts[:depth])
        for rel in bundled
        for depth in range(1, len(rel.parts))
    }
    tree = [
        path
        for name in sorted({rel.parts[0] for rel in bundled})
        if (dest / name).is_dir()
        for path in sorted((dest / name).rglob('*'))
    ]
    dirs = [path for path in tree if path.is_dir() and not path.is_symlink()]
    files = [path for path in tree if path not in known and path not in dirs]
    return files, [path for path in reversed(dirs) if path not in needed]
