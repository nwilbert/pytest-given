"""File glossaries: a Markdown file read into a Glossary, accessed by name."""

from abc import abstractmethod
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
    unique_avoid,
)
from .markdown_glossary import (
    ColumnSpec,
    GlossaryRow,
    has_tables,
    has_term_lines,
    parse_glossary_tables,
)
from .source import file_source

_KIND_ALIASES: dict[str, TermKind] = {
    'actor': 'actor',
    'object': 'object',
    'work object': 'object',
    'work_object': 'object',
    'activity': 'activity',
}


class _MarkdownFileGlossary(LookupGlossary):
    """A glossary loaded from a Markdown file. Access terms by name:
    g['Guest'].

    A `Glossary` rather than a wrapper around one, since every consumer of a
    glossary wants the storage. A subclass supplies the reader.
    """

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self._path = Path(path)
        try:
            text = self._path.read_text(encoding='utf-8')
        except FileNotFoundError as exc:
            raise PytestGivenError(f'glossary file not found: {self._path}.') from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise PytestGivenError(
                f'cannot read glossary file {self._path}: {exc}'
            ) from exc
        try:
            rows = self._read(text)
        except PytestGivenError as exc:
            hint = self._hint(text)
            suffix = f' ({hint})' if hint else ''
            raise PytestGivenError(f'{self._path}: {exc}{suffix}') from exc
        for row in rows:
            self._add_row(row)

    @abstractmethod
    def _read(self, text: str) -> list[GlossaryRow]: ...

    @abstractmethod
    def _hint(self, text: str) -> str | None:
        """What to add to a reader's error when the file looks like the other
        format's."""

    def _add_row(self, row: GlossaryRow) -> None:
        try:
            term_id = TermId(id_derive(row.term))
            term = GlossaryTerm(
                id=term_id,
                kind=self._parse_kind(row.kind),
                canonical=row.term,
                definition=normalize_definition(row.definition),
                source=file_source(self._path, row.line),
                section=row.section,
                avoid=unique_avoid(row.avoid),
            )
            register_or_conflict(
                self,
                term,
                lambda _existing: (
                    f'term {row.term!r} (id {term_id!r}) conflicts with an earlier row.'
                ),
            )
        except PytestGivenError as exc:
            raise PytestGivenError(f'{self._path}:{row.line}: {exc}') from exc

    @staticmethod
    def _parse_kind(raw: str | None) -> TermKind | None:
        if raw is None:
            return None
        mapped = _KIND_ALIASES.get(raw.lower())
        if mapped is None:
            raise PytestGivenError(
                f'unrecognized kind {raw!r}; expected one of '
                f"'actor', 'object'/'work object', 'activity'."
            )
        return mapped

    def __call__(self, name: str) -> TermHandle:
        # A file glossary is a closed vocabulary: the call form looks up only,
        # never creates. Unknown names raise (same as the subscript).
        return self[name]


class TableGlossary(_MarkdownFileGlossary):
    """A glossary read from the pipe tables of a Markdown file."""

    def __init__(
        self,
        path: str | Path,
        *,
        term_column: ColumnSpec = 0,
        definition_column: ColumnSpec = 1,
        kind_column: ColumnSpec | None = None,
        avoid_column: ColumnSpec | None = None,
    ) -> None:
        self._columns = (term_column, definition_column, kind_column, avoid_column)
        super().__init__(path)

    def _read(self, text: str) -> list[GlossaryRow]:
        term_column, definition_column, kind_column, avoid_column = self._columns
        return parse_glossary_tables(
            text,
            term_column=term_column,
            definition_column=definition_column,
            kind_column=kind_column,
            avoid_column=avoid_column,
        )

    def _hint(self, text: str) -> str | None:
        if not has_tables(text) and has_term_lines(text):
            return 'for `**Term**:` paragraphs, use `ParagraphGlossary`'
        return None
