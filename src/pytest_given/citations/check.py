"""`check_citations` is the whole job — read every document, compute every
finding and edit, and only then write — so a document that cannot be read
leaves every file as it was.
"""

import itertools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple
from urllib.parse import SplitResult, unquote, urlsplit

from ..model import STATUSES, PytestGivenError, ReportData, ReportUrl
from ..report import (
    CITATION_GLYPH,
    NO_SCENARIOS_SUMMARY,
    STATUS_GLYPH,
    SUMMARY_SEPARATOR,
    Target,
    fold_whitespace,
    link_text,
    plain_link_text,
    report_fragment,
)
from .markdown_links import VARIATION_SELECTOR, MarkdownLink, scan_links
from .targets import TargetResolver, parse_fragment

type FindingKind = Literal[
    'repointed', 'fragment', 'missing', 'stale', 'failed', 'mistyped', 'stray-summary'
]


@dataclass(frozen=True, kw_only=True)
class CitationFinding:
    path: Path
    line: int
    kind: FindingKind
    message: str
    details: tuple[str, ...] = ()
    fixed_by_update: bool

    def lines(self) -> list[str]:
        return [
            f'{self.path.as_posix()}:{self.line}: {self.message}',
            *(f'    {detail}' for detail in self.details),
        ]


@dataclass(frozen=True)
class CitationsResult:
    """Every finding, and the documents an update rewrote."""

    findings: list[CitationFinding]
    updated: list[Path]

    @property
    def remaining(self) -> list[CitationFinding]:
        return [finding for finding in self.findings if not finding.fixed_by_update]


def markdown_documents(paths: list[Path]) -> list[Path]:
    """The documents `paths` name: a file as given, a directory searched
    recursively for `*.md` — the shell cannot be trusted to expand a glob, as
    PowerShell does not for native commands."""
    documents: list[Path] = []
    for path in paths:
        if path.is_dir():
            documents.extend(sorted(path.rglob('*.md')))
        elif path.is_file():
            documents.append(path)
        else:
            raise PytestGivenError(
                f'{path.as_posix()} is neither a Markdown file nor a directory.'
            )
    return documents


def check_citations(
    report: ReportData,
    documents: list[Path],
    *,
    report_url: ReportUrl | None,
    report_path: Path | None,
    update: bool,
) -> CitationsResult:
    location = _ReportLocation(
        report_url or report.metadata.report_url,
        None if report_path is None else report_path.resolve(),
    )
    if location.url is None and location.path is None:
        raise PytestGivenError(
            'No report URL is known — the report stores none and --report-url is '
            'not given — and no --report-path either, so no link can be told to '
            'point at the report.'
        )
    resolver = TargetResolver(report)
    texts = {path: _read(path) for path in documents}
    findings: list[CitationFinding] = []
    edited: dict[Path, str] = {}
    for path, text in texts.items():
        document_findings, edits = _check_document(path, text, resolver, location)
        findings.extend(document_findings)
        if update and edits:
            edited[path] = _apply(text, edits)
    updated = [path for path, text in edited.items() if text != texts[path]]
    for path in updated:
        path.write_bytes(edited[path].encode('utf-8'))
    return CitationsResult(findings=findings, updated=updated)


class _ReportLocation:
    """Where the report is served and where it sits, to tell a link to it from
    any other. A link's query is no part of it, as a static page ignores one."""

    def __init__(self, url: str | None, path: Path | None) -> None:
        self.url = None if url is None else urlsplit(url)._replace(query='')
        # Resolved, as each relative link's path is before it is compared.
        self.path = path
        # A document links the report by the same few paths, again and again.
        self._resolved: dict[Path, Path] = {}

    def names_report(self, link: SplitResult, document: Path) -> bool:
        if link.scheme or link.netloc:
            return link._replace(query='') == self.url
        if link.path.startswith('/'):
            return self.url is not None and unquote(link.path) == unquote(self.url.path)
        relative = unquote(link.path)
        # No file is named so, and resolving the name raises on POSIX alone.
        if self.path is None or '\0' in relative:
            return False
        joined = document.parent / relative
        if joined not in self._resolved:
            self._resolved[joined] = joined.resolve()
        return self._resolved[joined] == self.path


class _Edit(NamedTuple):
    start: int
    end: int
    text: str


# Also read as a citation's glyph, and rewritten as emoji: the Markdown sink's
# glyphs and a typed `?`, so a hand-typed placeholder works either way.
_READ_GLYPHS = (*CITATION_GLYPH.values(), *STATUS_GLYPH.values(), '?')
_SUMMARY_COUNT = (
    r'\d+ (?:'
    + '|'.join(CITATION_GLYPH[status] for status in STATUSES)
    + f'){VARIATION_SELECTOR}?'
)
# Only text of a summary's shape counts as one, so a parenthetical of the
# author's own after a citation stays theirs. A hard wrap may put it on the
# next line.
_SUMMARY = re.compile(
    r'(?:[ \t]+|[ \t]*\n[ \t]*)'
    rf'({re.escape(NO_SCENARIOS_SUMMARY)}'
    rf'|\({_SUMMARY_COUNT}(?:{re.escape(SUMMARY_SEPARATOR)}{_SUMMARY_COUNT})*\))'
)


def _read(path: Path) -> str:
    """The document's text, line endings untranslated, so an update rewrites
    no byte it does not mean to."""
    try:
        return path.read_bytes().decode('utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise PytestGivenError(f'Cannot read {path.as_posix()}: {error}') from error


def _check_document(
    path: Path, text: str, resolver: TargetResolver, location: _ReportLocation
) -> tuple[list[CitationFinding], list[_Edit]]:
    findings: list[CitationFinding] = []
    edits: list[_Edit] = []
    for link in scan_links(text, _READ_GLYPHS):
        fragment = _report_fragment(link.destination, path, location)
        if fragment is not None:
            _LinkCheck(path, link, resolver, findings, edits).run(fragment)
    return findings, edits


def _report_fragment(url: str, document: Path, location: _ReportLocation) -> str | None:
    """The fragment of a link to the report, or None for a link elsewhere —
    as it is for a URL no parser reads, which no reader can open either."""
    base, _, fragment = url.partition('#')
    if not base:
        return None
    try:
        link = urlsplit(base)
    except ValueError:
        return None
    return fragment if location.names_report(link, document) else None


@dataclass
class _LinkCheck:
    path: Path
    link: MarkdownLink
    resolver: TargetResolver
    findings: list[CitationFinding]
    edits: list[_Edit]

    def run(self, fragment: str) -> None:
        is_citation = self.link.glyph is not None
        target = parse_fragment(fragment)
        if target is None:
            if is_citation:
                self._find(
                    'mistyped',
                    f'citation links the report, but #{fragment} names no scenario, '
                    'tag or story',
                )
            return
        resolved = self.resolver.resolve(target)
        if resolved is not None and resolved != target:
            self._repoint(
                'fragment',
                f'{target.kind} fragment names {target.key!r}, which a report link '
                f'names as {resolved.key!r}',
                target,
                resolved,
            )
        written_title = plain_link_text(
            self.link.text, in_table_row=self.link.in_table_row
        )
        if resolved is None and is_citation and target.kind == 'scenario':
            titled = self.resolver.scenarios_titled(written_title)
            if len(titled) == 1:
                resolved = Target('scenario', titled[0])
                self._repoint(
                    'repointed',
                    f'{_named(target)} is not in the report; its link text is '
                    f'the title of {titled[0]}',
                    target,
                    resolved,
                )
        if resolved is None:
            self._find(
                'missing',
                f'{_named(target)} is not in the report',
                *self.resolver.suggestions(target, written_title),
            )
            if is_citation:
                self._mark_missing()
            return
        if is_citation:
            self._check_citation(resolved, written_title)

    def _check_citation(self, target: Target, written_title: str) -> None:
        citation = self.resolver.index.citation(target)
        link = self.link
        assert link.glyph is not None
        if link.glyph.bare != citation.glyph:
            self._find(
                'stale',
                'stale glyph',
                f'{link.glyph.text} → {citation.glyph}',
                fixed=True,
            )
            self.edits.append(_Edit(*link.glyph.span, citation.glyph))
        if written_title != fold_whitespace(citation.title):
            self._find(
                'stale',
                'stale link text',
                f'{written_title} → {citation.title}',
                fixed=True,
            )
            self.edits.append(
                _Edit(
                    *link.text_span,
                    link_text(citation.title, in_table_row=link.in_table_row),
                )
            )
        summary = _SUMMARY.match(link.trailing)
        if citation.summary is None:
            if summary is not None:
                self._find(
                    'stray-summary',
                    f'a scenario citation takes no summary: {summary.group(1)}',
                )
        elif summary is None:
            self._find('stale', 'missing summary', f'→ {citation.summary}', fixed=True)
            self.edits.append(_Edit(link.end, link.end, f' {citation.summary}'))
        elif summary.group(1).replace(VARIATION_SELECTOR, '') != citation.summary:
            self._find(
                'stale',
                'stale summary',
                f'{summary.group(1)} → {citation.summary}',
                fixed=True,
            )
            self.edits.append(
                _Edit(*link.trailing_span(*summary.span(1)), citation.summary)
            )
        if citation.state == 'failed':
            self._find('failed', f'cited {target.kind} fails: {citation.title}')

    def _mark_missing(self) -> None:
        link = self.link
        assert link.glyph is not None
        missing = CITATION_GLYPH['missing']
        if link.glyph.bare != missing:
            self.edits.append(_Edit(*link.glyph.span, missing))
        if summary := _SUMMARY.match(link.trailing):
            self.edits.append(_Edit(*link.trailing_span(0, summary.end()), ''))

    def _repoint(
        self, kind: FindingKind, message: str, old: Target, new: Target
    ) -> None:
        new_fragment = report_fragment(new)
        self._find(
            kind, message, f'#{report_fragment(old)} → #{new_fragment}', fixed=True
        )
        span = self.link.fragment_span
        assert span is not None
        self.edits.append(_Edit(*span, new_fragment))

    def _find(
        self, kind: FindingKind, message: str, *details: str, fixed: bool = False
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


def _named(target: Target) -> str:
    if target.key:
        return f'{target.kind} {target.key}'
    return f'a {target.kind} with an empty name'


def _apply(text: str, edits: list[_Edit]) -> str:
    ordered = sorted(edits)
    for edit, following in itertools.pairwise(ordered):
        assert edit.end <= following.start, (
            f'overlapping citation edits: {edit}, {following}'
        )
    for edit in reversed(ordered):
        text = text[: edit.start] + edit.text + text[edit.end :]
    return text
