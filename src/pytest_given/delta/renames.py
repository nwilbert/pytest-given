"""The rename log, `given-renames.toml`: identity changes the delta cannot
detect by itself, authored and committed with the project."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

from ..model import PytestGivenError, case_suffix

DEFAULT_RENAMES_PATH = Path('given-renames.toml')

type EntryTable = Literal['scenario', 'term']

_TABLES: tuple[EntryTable, ...] = get_args(EntryTable.__value__)
_KEYS = {
    'scenario': frozenset({'old', 'new', 'cases', 'rev'}),
    'term': frozenset({'old', 'new', 'rev'}),
}


@dataclass(frozen=True, kw_only=True)
class RenameEntry:
    table: EntryTable
    position: int  # 1-based within its table, for messages
    old: str
    new: str | None = None
    cases: Mapping[str, str] = field(default_factory=dict)
    rev: str | None = None

    @property
    def label(self) -> str:
        return f'{_entry_name(self.table, self.position)} (old = "{self.old}")'


@dataclass(frozen=True, kw_only=True)
class RenameLog:
    """Each table in file order. `tomllib` drops how the two interleave, and
    chains only ever follow one table."""

    entries: tuple[RenameEntry, ...] = ()

    def of(self, table: EntryTable) -> tuple[RenameEntry, ...]:
        return tuple(entry for entry in self.entries if entry.table == table)

    def revs(self) -> frozenset[str]:
        return frozenset(entry.rev for entry in self.entries if entry.rev is not None)


def read_rename_log(path: Path | None) -> RenameLog:
    """`None` reads the default file when it exists. A path given must exist."""
    if path is None:
        if not DEFAULT_RENAMES_PATH.is_file():
            return RenameLog()
        path = DEFAULT_RENAMES_PATH
    elif not path.is_file():
        raise PytestGivenError(f'rename log not found: {path}')
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError as error:
        raise PytestGivenError(f'{path}: not valid UTF-8: {error}') from error
    return parse_rename_log(text, str(path))


def parse_rename_log(text: str, source: str) -> RenameLog:
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise PytestGivenError(f'{source}: not valid TOML: {error}') from error
    unknown_tables = sorted(set(document) - set(_TABLES))
    if unknown_tables:
        raise PytestGivenError(
            f'{source}: unknown table [[{unknown_tables[0]}]], expected '
            '[[scenario]] or [[term]]'
        )
    entries: list[RenameEntry] = []
    for table in _TABLES:
        raw_entries = document.get(table, [])
        if not isinstance(raw_entries, list) or not all(
            isinstance(raw, dict) for raw in raw_entries
        ):
            raise PytestGivenError(
                f'{source}: `{table}` must be an array of tables ([[{table}]])'
            )
        for position, raw in enumerate(raw_entries, start=1):
            entries.append(_entry(table, position, raw, source))
    return RenameLog(entries=tuple(entries))


def _entry(
    table: EntryTable, position: int, raw: dict[str, object], source: str
) -> RenameEntry:
    name = _entry_name(table, position)
    old = raw.get('old')
    if not isinstance(old, str):
        raise PytestGivenError(f'{source}: {name} needs `old` as a string')
    where = f'{source}: {name} (old = "{old}")'
    unknown_keys = sorted(set(raw) - _KEYS[table])
    if unknown_keys:
        raise PytestGivenError(
            f'{where}: unknown key `{unknown_keys[0]}`, expected one of '
            f'{", ".join(f"`{key}`" for key in sorted(_KEYS[table]))}'
        )
    new = _string(raw, 'new', where)
    rev = _string(raw, 'rev', where)
    cases = _cases(raw.get('cases', {}), where)
    if new is None and not cases:
        needs = '`new`' if table == 'term' else '`new` or `cases`'
        raise PytestGivenError(f'{where}: needs {needs}')
    for key, value in (('old', old), ('new', new)):
        if value is not None and case_suffix(value):
            raise PytestGivenError(
                f'{where}: `{key}` must not end in a parametrize tail '
                f'({case_suffix(value)}), rename a case through `cases`'
            )
    if rev is not None and rev.startswith('-'):
        raise PytestGivenError(f'{where}: `rev` must not start with "-": {rev!r}')
    return RenameEntry(
        table=table, position=position, old=old, new=new, cases=cases, rev=rev
    )


def _string(raw: dict[str, object], key: str, where: str) -> str | None:
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise PytestGivenError(f'{where}: `{key}` must be a string')
    return value


def _cases(raw: object, where: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise PytestGivenError(
            f'{where}: `cases` must be a table of old = "new" case IDs'
        )
    for old_id, new_id in raw.items():
        if not isinstance(new_id, str):
            raise PytestGivenError(
                f'{where}: `cases` value for {old_id!r} must be a string'
            )
    return raw


def _entry_name(table: EntryTable, position: int) -> str:
    return f'[[{table}]] #{position}'
