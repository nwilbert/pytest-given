"""File-backed glossary: parse a Markdown file into a Glossary, accessed by name."""

from pathlib import Path
from typing import Literal

from ..model import (
    Glossary,
    GlossaryTerm,
    PytestGivenError,
    TermId,
    id_derive,
)
from .glossary import (
    DeferredTermHandle,
    _normalize_definition,
    deferred_handle_or_raise,
    terms_match,
)
from .markdown_glossary import ColumnSpec, GlossaryRow, parse_glossary_tables
from .source import file_source

_KIND_ALIASES: dict[str, Literal['actor', 'object', 'verb']] = {
    'actor': 'actor',
    'object': 'object',
    'work object': 'object',
    'work_object': 'object',
    'verb': 'verb',
}


class FileGlossary:
    """Glossary loaded from a Markdown file. Access terms by name: g['Guest']."""

    def __init__(
        self,
        path: str | Path,
        *,
        term_column: ColumnSpec = 0,
        description_column: ColumnSpec = 1,
        kind_column: ColumnSpec | None = None,
    ) -> None:
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
        self._glossary = Glossary()
        self._handles: dict[TermId, DeferredTermHandle] = {}
        for row in rows:
            self._add_row(row)

    @property
    def glossary(self) -> Glossary:
        return self._glossary

    def _add_row(self, row: GlossaryRow) -> None:
        try:
            term_id = id_derive(row.term)
        except PytestGivenError as exc:
            raise PytestGivenError(f'{self._path}:{row.line}: {exc}') from exc
        kind = self._parse_kind(row.kind, row.line)
        term = GlossaryTerm(
            id=term_id,
            kind=kind,
            canonical=row.term,
            definition=_normalize_definition(row.definition),
            source=file_source(self._path, row.line),
        )
        existing = self._glossary.get(term_id)
        if existing is not None:
            if not terms_match(existing, term):
                raise PytestGivenError(
                    f'{self._path}:{row.line}: term {row.term!r} (id {term_id!r}) '
                    f'conflicts with an earlier row.'
                )
            return
        self._glossary._register(term)

    def _parse_kind(
        self, raw: str | None, line: int
    ) -> Literal['actor', 'object', 'verb'] | None:
        if raw is None:
            return None
        mapped = _KIND_ALIASES.get(raw.lower())
        if mapped is None:
            raise PytestGivenError(
                f'{self._path}:{line}: unrecognised kind {raw!r}; expected one of '
                f"'actor', 'object'/'work object', 'verb'."
            )
        return mapped

    def __getitem__(self, name: str) -> DeferredTermHandle:
        return deferred_handle_or_raise(self._glossary, name, self._handles)

    def __call__(self, name: str) -> DeferredTermHandle:
        # A FileGlossary is a closed vocabulary: the call form looks up only,
        # never creates. Unknown names raise (same as the subscript).
        return self[name]
