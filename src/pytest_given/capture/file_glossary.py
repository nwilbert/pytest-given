"""File-backed glossary: parse a Markdown file into a Glossary, accessed by name."""

from pathlib import Path

from ..model import (
    GlossaryTerm,
    PytestGivenError,
    TermId,
    TermKind,
    id_derive,
)
from .glossary import (
    LookupGlossary,
    TermHandle,
    normalize_definition,
    register_or_conflict,
)
from .markdown_glossary import ColumnSpec, GlossaryRow, parse_glossary_tables
from .source import file_source

_KIND_ALIASES: dict[str, TermKind] = {
    'actor': 'actor',
    'object': 'object',
    'work object': 'object',
    'work_object': 'object',
    'verb': 'verb',
}


class FileGlossary(LookupGlossary):
    """Glossary loaded from a Markdown file. Access terms by name: g['Guest'].

    A `Glossary` rather than a wrapper around one: everything that consumes a
    glossary — `resolve_glossary`, the report model, the name lookup — wants
    the storage, and an `isinstance` that answered False for half the user-
    facing glossaries made every one of those sites carry a second arm.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        term_column: ColumnSpec = 0,
        description_column: ColumnSpec = 1,
        kind_column: ColumnSpec | None = None,
    ) -> None:
        super().__init__()
        self._path = Path(path)
        try:
            text = self._path.read_text(encoding='utf-8')
        except FileNotFoundError as exc:
            raise PytestGivenError(f'glossary file not found: {self._path}.') from exc
        rows = parse_glossary_tables(
            text,
            term_column=term_column,
            description_column=description_column,
            kind_column=kind_column,
        )
        for row in rows:
            self._add_row(row)

    def _add_row(self, row: GlossaryRow) -> None:
        try:
            term_id = TermId(id_derive(row.term))
        except PytestGivenError as exc:
            raise PytestGivenError(f'{self._path}:{row.line}: {exc}') from exc
        kind = self._parse_kind(row.kind, row.line)
        term = GlossaryTerm(
            id=term_id,
            kind=kind,
            canonical=row.term,
            definition=normalize_definition(row.definition),
            source=file_source(self._path, row.line),
        )
        register_or_conflict(
            self,
            term,
            lambda _existing: (
                f'{self._path}:{row.line}: term {row.term!r} (id {term_id!r}) '
                f'conflicts with an earlier row.'
            ),
        )

    def _parse_kind(self, raw: str | None, line: int) -> TermKind | None:
        if raw is None:
            return None
        mapped = _KIND_ALIASES.get(raw.lower())
        if mapped is None:
            raise PytestGivenError(
                f'{self._path}:{line}: unrecognized kind {raw!r}; expected one of '
                f"'actor', 'object'/'work object', 'verb'."
            )
        return mapped

    def __call__(self, name: str) -> TermHandle:
        # A FileGlossary is a closed vocabulary: the call form looks up only,
        # never creates. Unknown names raise (same as the subscript).
        return self[name]
