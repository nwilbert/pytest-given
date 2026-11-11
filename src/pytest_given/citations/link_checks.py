"""The rules one report link is held to: what a check finds on it, and the
edits that would make it current.

A link is written as a Markdown link or as a `<details>` citation. The rules
are the same for both, and each shape reads and writes its link text in its
own markup.
"""

import itertools
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Literal, NamedTuple, Protocol

from ..markdown import Span, plain_html_text, plain_link_text
from ..report import (
    CITATION_GLYPH,
    Citation,
    Target,
    citation_body_md,
    link_text,
    report_fragment,
)
from .details import DetailsCitation
from .markdown_links import (
    SUMMARY_PATTERN,
    VARIATION_SELECTOR,
    Glyph,
    MarkdownLink,
    WrittenSummary,
)
from .targets import (
    TargetResolver,
    TitleForm,
    parse_fragment,
    shown_title,
    target_label,
)

type CitationFindingKind = Literal[
    'repointed',
    'fragment',
    'missing',
    'stale',
    'failed',
    'mistyped',
    'stray-summary',
    'stray-narration',
]


@dataclass(frozen=True, kw_only=True)
class CitationFinding:
    path: Path
    line: int
    kind: CitationFindingKind
    message: str
    details: tuple[str, ...] = ()
    fixed_by_update: bool

    def lines(self) -> list[str]:
        message, *details = self.unlocated_lines()
        return [f'{self.path.as_posix()}:{self.line}: {message}', *details]

    def unlocated_lines(self) -> list[str]:
        return [self.message, *(f'    {detail}' for detail in self.details)]


@dataclass(frozen=True, kw_only=True)
class ReportLink:
    """A report link with its own findings, as two may share a line. `named`
    is its target as written; `resolved`, as the report holds it."""

    path: Path
    line: int
    glyph: str | None
    named: str
    resolved: Target | None
    findings: tuple[CitationFinding, ...]

    def lines(self) -> list[str]:
        return [
            f'{self.path.as_posix()}:{self.line}: {self.glyph or "link"} {self.named}',
            *(
                f'    {line}'
                for finding in self.findings
                for line in finding.unlocated_lines()
            ),
        ]


class Edit(NamedTuple):
    start: int
    end: int
    text: str


# A hard wrap may put a summary on the next line.
_TRAILING_SUMMARY = re.compile(rf'(?:[ \t]+|[ \t]*\n[ \t]*)({SUMMARY_PATTERN})')


class _CitingLink(Protocol):
    """A report link in either shape a document writes one."""

    @property
    def line(self) -> int: ...

    @property
    def glyph(self) -> Glyph | None: ...

    @property
    def text_span(self) -> Span: ...

    @property
    def end(self) -> int:
        """Where a summary goes, just past the link."""
        ...

    @property
    def destination(self) -> str: ...

    @property
    def fragment_span(self) -> Span | None: ...


@dataclass
class _LinkCheck[L: _CitingLink](ABC):
    """The rules every report link is held to; a link shape reads and writes
    its link text in its own markup."""

    title_form: ClassVar[TitleForm]
    path: Path
    link: L
    resolver: TargetResolver
    edits: list[Edit]
    findings: list[CitationFinding] = field(default_factory=list, init=False)

    def run(self, fragment: str) -> ReportLink | None:
        """The link checked, or None for a plain link naming no target — not
        a report link."""
        target = parse_fragment(fragment)
        if target is None:
            if self.link.glyph is None:
                return None
            self._find(
                'mistyped',
                f'citation links the report, but #{fragment} names no scenario, '
                'tag, story or term',
            )
            return self._checked(f'#{fragment}', None)
        return self._checked(target_label(target), self._check_target(target))

    @abstractmethod
    def _written_title(self) -> str:
        """The link text as the title it is compared with."""

    @abstractmethod
    def _link_text(self, citation: Citation) -> str: ...

    @abstractmethod
    def _written_summary(self) -> WrittenSummary | None: ...

    def _check_target(self, target: Target) -> Target | None:
        glyph = self.link.glyph
        written_title = self._written_title()
        resolved = self._resolve_and_repoint(target, glyph, written_title)
        if resolved is None:
            self._find(
                'missing',
                f'{target_label(target)} is not in the report',
                *self.resolver.suggestions(target, written_title, self.title_form),
            )
            if glyph is not None:
                self._mark_missing(glyph)
        elif glyph is not None:
            self._check_citation(resolved, glyph, written_title)
        return resolved

    def _checked(self, label: str, resolved: Target | None) -> ReportLink:
        glyph = self.link.glyph
        return ReportLink(
            path=self.path,
            line=self.link.line,
            glyph=None if glyph is None else glyph.text,
            named=label,
            resolved=resolved,
            findings=tuple(self.findings),
        )

    def _resolve_and_repoint(
        self, target: Target, glyph: Glyph | None, written_title: str
    ) -> Target | None:
        """The target as a citation names it now, the fragment repointed to it —
        for a scenario citation the report lacks, the one titled as its text."""
        resolved = self.resolver.resolve(target)
        if resolved is not None:
            if resolved != target:
                self._repoint(
                    'fragment',
                    f'{target.kind} fragment names {target.key!r}, which a report '
                    f'link names as {resolved.key!r}',
                    target,
                    resolved,
                )
            return resolved
        if glyph is None or target.kind != 'scenario':
            return None
        titled = self.resolver.scenarios_titled(written_title, self.title_form)
        if len(titled) != 1:
            return None
        resolved = Target('scenario', titled[0])
        self._repoint(
            'repointed',
            f'{target_label(target)} is not in the report; its link text is the title '
            f'of {titled[0]}',
            target,
            resolved,
        )
        return resolved

    def _check_citation(self, target: Target, glyph: Glyph, written_title: str) -> None:
        citation = self.resolver.index.citation(target)
        if glyph.bare != citation.glyph:
            self._fix(
                'stale glyph',
                Edit(*glyph.span, citation.glyph),
                f'{glyph.text} → {citation.glyph}',
            )
        shown = shown_title(citation.title, self.title_form)
        if written_title != shown:
            self._fix(
                'stale link text',
                Edit(*self.link.text_span, self._link_text(citation)),
                f'{written_title} → {shown}',
            )
        self._check_summary(citation)
        if citation.state == 'failed':
            # A term itself cannot fail.
            failing = (
                'a scenario using cited term'
                if target.kind == 'term'
                else f'cited {target.kind}'
            )
            self._find('failed', f'{failing} fails: {citation.title_text}')

    def _check_summary(self, citation: Citation) -> None:
        match citation.summary, self._written_summary():
            case None, (str() as written, _):
                self._find(
                    'stray-summary',
                    f'a scenario citation takes no summary: {written}',
                )
            case str() as summary, None:
                self._fix(
                    'missing summary',
                    Edit(self.link.end, self.link.end, f' {summary}'),
                    f'→ {summary}',
                )
            case str() as summary, (str() as written, span) if (
                written.replace(VARIATION_SELECTOR, '') != summary
            ):
                self._fix(
                    'stale summary',
                    Edit(*span, summary),
                    f'{written} → {summary}',
                )

    def _mark_missing(self, glyph: Glyph) -> None:
        missing = CITATION_GLYPH['missing']
        if glyph.bare != missing:
            self.edits.append(Edit(*glyph.span, missing))
        if written := self._written_summary():
            self.edits.append(Edit(self.link.end, written.span[1], ''))

    def _repoint(
        self, kind: CitationFindingKind, message: str, old: Target, new: Target
    ) -> None:
        span = self.link.fragment_span
        assert span is not None
        new_fragment = report_fragment(new)
        self._fix(
            message,
            Edit(*span, new_fragment),
            f'#{report_fragment(old)} → #{new_fragment}',
            kind=kind,
        )

    def _fix(
        self,
        message: str,
        edit: Edit,
        *details: str,
        kind: CitationFindingKind = 'stale',
    ) -> None:
        self._find(kind, message, *details, fixed=True)
        self.edits.append(edit)

    def _find(
        self,
        kind: CitationFindingKind,
        message: str,
        *details: str,
        fixed: bool = False,
    ) -> None:
        self.findings.append(
            CitationFinding(
                path=self.path,
                line=self.link.line,
                kind=kind,
                message=message,
                details=details,
                fixed_by_update=fixed,
            )
        )


class MarkdownCheck(_LinkCheck[MarkdownLink]):
    title_form = 'markdown'

    def _written_title(self) -> str:
        return plain_link_text(self.link.text, in_table_row=self.link.in_table_row)

    def _link_text(self, citation: Citation) -> str:
        return link_text(citation.title, in_table_row=self.link.in_table_row)

    def _written_summary(self) -> WrittenSummary | None:
        written = _TRAILING_SUMMARY.match(self.link.trailing)
        if written is None:
            return None
        return WrittenSummary(
            written.group(1), self.link.trailing_span(*written.span(1))
        )


@dataclass
class DetailsCheck(_LinkCheck[DetailsCitation]):
    """A citation's rules, written as HTML, plus its opening tag and body: a
    scenario's narration or a term's definition. A tag or story has neither."""

    title_form = 'html'
    line_break: str
    owns_body: bool = field(default=False, init=False)

    def _written_title(self) -> str:
        return plain_html_text(self.link.text)

    def _link_text(self, citation: Citation) -> str:
        return citation.html_link_text

    def _written_summary(self) -> WrittenSummary | None:
        return self.link.summary

    def _check_target(self, target: Target) -> Target | None:
        if target.kind not in _BODY_NOUN:
            self._find(
                'stray-narration', f'a {target.kind} citation takes no narration'
            )
            return self.resolver.resolve(target)
        resolved = super()._check_target(target)
        self._check_opening_tag()
        if resolved is not None:
            self.owns_body = True
            self._check_body(resolved)
        return resolved

    def _check_opening_tag(self) -> None:
        if self.link.markdown == '1':
            return
        tag = self.link.opening_tag
        start, end = self.link.markdown_attribute
        offset = self.link.opening_tag_span[0]
        self._fix(
            'stale opening tag',
            Edit(offset + start, offset + end, _MARKDOWN_1),
            f'{tag} → {tag[:start]}{_MARKDOWN_1}{tag[end:]}',
        )

    def _check_body(self, target: Target) -> None:
        """Compared past its container prefixes, line breaks normalized;
        written back with the document's line break."""
        written = self.link.body
        expected = citation_body_md(self.resolver.index.cited(target))
        if written == expected:
            return
        written_line, expected_line = next(
            pair
            for pair in itertools.zip_longest(written.split('\n'), expected.split('\n'))
            if pair[0] != pair[1]
        )
        self._fix(
            f'stale {_BODY_NOUN[target.kind]}',
            Edit(
                *self.link.body_span,
                self.link.written_body(expected, self.line_break),
            ),
            f'written: {_body_line(written_line)}',
            f'expected: {_body_line(expected_line)}',
        )


_MARKDOWN_1 = ' markdown="1"'
# What a `<details>` citation's body holds, for the kinds that take one.
_BODY_NOUN = {'scenario': 'narration', 'term': 'definition'}


def _body_line(line: str | None) -> str:
    if line is None:
        return '(end of body)'
    return line or '(blank line)'
