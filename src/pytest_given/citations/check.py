"""`check_citations` is the whole job — read every document, compute every
finding and edit, and only then write — so a document that cannot be read
leaves every file as it was.
"""

import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Literal, NamedTuple
from urllib.parse import SplitResult, unquote, urlsplit

from ..markdown import fold_whitespace, plain_link_text
from ..model import (
    STATUSES,
    NodeId,
    PytestGivenError,
    ReportData,
    ReportUrl,
    node_base,
)
from ..report import (
    CITATION_GLYPH,
    NO_SCENARIOS_SUMMARY,
    STATUS_GLYPH,
    SUMMARY_SEPARATOR,
    Target,
    link_text,
    report_fragment,
)
from .markdown_links import VARIATION_SELECTOR, Glyph, MarkdownLink, scan_links
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


@dataclass(frozen=True)
class CitationsResult:
    """Every report link, those `covering` lists, and the documents an update
    rewrote."""

    links: list[ReportLink]
    listed: list[ReportLink]
    updated: list[Path]

    @cached_property
    def findings(self) -> list[CitationFinding]:
        return [finding for link in self.links for finding in link.findings]

    @cached_property
    def remaining(self) -> list[CitationFinding]:
        return [finding for finding in self.findings if not finding.fixed_by_update]

    @property
    def left_out(self) -> int:
        """The findings on links `covering` leaves out."""
        return len(self.findings) - sum(len(link.findings) for link in self.listed)


def markdown_documents(paths: list[Path]) -> list[Path]:
    """The documents `paths` name, each once: a file as given, a directory
    searched recursively for `*.md` files — the shell cannot be trusted to
    expand a glob, as PowerShell does not for native commands."""
    documents: dict[Path, Path] = {}
    for path in paths:
        if path.is_dir():
            found = sorted(match for match in path.rglob('*.md') if match.is_file())
        elif path.is_file():
            found = [path]
        else:
            raise PytestGivenError(
                f'{path.as_posix()} is neither a Markdown file nor a directory.'
            )
        for document in found:
            documents.setdefault(document.resolve(), document)
    return list(documents.values())


def check_citations(
    report: ReportData,
    documents: list[Path],
    *,
    report_url: ReportUrl | None,
    report_path: Path | None,
    update: bool,
    covering: Sequence[str] = (),
) -> CitationsResult:
    """`covering` names scenarios by any name a report link may give them;
    the result lists the links that may cite one — every link, when it names
    none."""
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
    covers = _Covering(resolver, covering)
    texts = {path: _read(path) for path in documents}
    links: list[ReportLink] = []
    edited: dict[Path, str] = {}
    for path, text in texts.items():
        document_links, edits = _check_document(path, text, resolver, location)
        links.extend(document_links)
        if update and edits:
            edited[path] = _apply(text, edits)
    updated = [path for path, text in edited.items() if text != texts[path]]
    for path in updated:
        path.write_bytes(edited[path].encode('utf-8'))
    return CitationsResult(
        links=links,
        listed=[link for link in links if covers(link.resolved)],
        updated=updated,
    )


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


class _Covering:
    """Whether a link's resolved target may cite a scenario `covering` names: is
    it, or a tag — through its prefixes — or story counting it. A link that
    resolves to nothing may be one under a name it no longer has."""

    def __init__(self, resolver: TargetResolver, covering: Sequence[str]) -> None:
        self._index = resolver.index
        self._ids: set[NodeId] = set()
        for node_id in covering:
            named = Target('scenario', node_id)
            resolved = resolver.resolve(named)
            # No link names a test function whose cases each are a scenario,
            # but covering it covers them all.
            scenarios = (
                [
                    scenario
                    for cited, scenario in self._index.scenarios.items()
                    if node_base(cited) == node_id
                ]
                if resolved is None
                else self._index.counted(resolved)
            )
            if not scenarios:
                raise PytestGivenError(
                    '; '.join(
                        [
                            f'{_named(named)} is not in the report',
                            *resolver.suggestions(named, ''),
                        ]
                    )
                )
            self._ids.update(scenario.id for scenario in scenarios)
        # A document links the same few tags and stories, again and again.
        self._covers: dict[Target, bool] = {}

    def __call__(self, resolved: Target | None) -> bool:
        if not self._ids or resolved is None:
            return True
        if resolved not in self._covers:
            self._covers[resolved] = any(
                scenario.id in self._ids for scenario in self._index.counted(resolved)
            )
        return self._covers[resolved]


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
    path: Path,
    text: str,
    resolver: TargetResolver,
    location: _ReportLocation,
) -> tuple[list[ReportLink], list[_Edit]]:
    links: list[ReportLink] = []
    edits: list[_Edit] = []
    for link in scan_links(text, _READ_GLYPHS):
        fragment = _report_fragment(link.destination, path, location)
        if fragment is not None:
            checked = _LinkCheck(path, link, resolver, edits).run(fragment)
            if checked is not None:
                links.append(checked)
    return links, edits


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
    edits: list[_Edit]
    findings: list[CitationFinding] = field(default_factory=list)

    def run(self, fragment: str) -> ReportLink | None:
        """The link checked, or None for a plain link naming no target — not
        a report link, as a glossary term's is not."""
        glyph = self.link.glyph
        target = parse_fragment(fragment)
        if target is None:
            if glyph is None:
                return None
            self._find(
                'mistyped',
                f'citation links the report, but #{fragment} names no scenario, '
                'tag or story',
            )
            return self._checked(f'#{fragment}', None)
        written_title = plain_link_text(
            self.link.text, in_table_row=self.link.in_table_row
        )
        resolved = self._resolve_and_repoint(target, glyph, written_title)
        if resolved is None:
            self._find(
                'missing',
                f'{_named(target)} is not in the report',
                *self.resolver.suggestions(target, written_title),
            )
            if glyph is not None:
                self._mark_missing(glyph)
        elif glyph is not None:
            self._check_citation(resolved, glyph, written_title)
        return self._checked(_named(target), resolved)

    def _checked(self, named: str, resolved: Target | None) -> ReportLink:
        glyph = self.link.glyph
        return ReportLink(
            path=self.path,
            line=self.link.line,
            glyph=None if glyph is None else glyph.text,
            named=named,
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
        titled = self.resolver.scenarios_titled(written_title)
        if len(titled) != 1:
            return None
        resolved = Target('scenario', titled[0])
        self._repoint(
            'repointed',
            f'{_named(target)} is not in the report; its link text is the title '
            f'of {titled[0]}',
            target,
            resolved,
        )
        return resolved

    def _check_citation(self, target: Target, glyph: Glyph, written_title: str) -> None:
        citation = self.resolver.index.citation(target)
        link = self.link
        if glyph.bare != citation.glyph:
            self._fix(
                'stale glyph',
                f'{glyph.text} → {citation.glyph}',
                _Edit(*glyph.span, citation.glyph),
            )
        if written_title != fold_whitespace(citation.title_text):
            self._fix(
                'stale link text',
                f'{written_title} → {citation.title_text}',
                _Edit(
                    *link.text_span,
                    link_text(citation.title, in_table_row=link.in_table_row),
                ),
            )
        match citation.summary, _SUMMARY.match(link.trailing):
            case None, re.Match() as written:
                self._find(
                    'stray-summary',
                    f'a scenario citation takes no summary: {written.group(1)}',
                )
            case str() as summary, None:
                self._fix(
                    'missing summary',
                    f'→ {summary}',
                    _Edit(link.end, link.end, f' {summary}'),
                )
            case str() as summary, re.Match() as written if (
                written.group(1).replace(VARIATION_SELECTOR, '') != summary
            ):
                self._fix(
                    'stale summary',
                    f'{written.group(1)} → {summary}',
                    _Edit(*link.trailing_span(*written.span(1)), summary),
                )
        if citation.state == 'failed':
            self._find('failed', f'cited {target.kind} fails: {citation.title_text}')

    def _mark_missing(self, glyph: Glyph) -> None:
        link = self.link
        missing = CITATION_GLYPH['missing']
        if glyph.bare != missing:
            self.edits.append(_Edit(*glyph.span, missing))
        if summary := _SUMMARY.match(link.trailing):
            self.edits.append(_Edit(*link.trailing_span(0, summary.end()), ''))

    def _repoint(
        self, kind: FindingKind, message: str, old: Target, new: Target
    ) -> None:
        span = self.link.fragment_span
        assert span is not None
        new_fragment = report_fragment(new)
        self._fix(
            message,
            f'#{report_fragment(old)} → #{new_fragment}',
            _Edit(*span, new_fragment),
            kind=kind,
        )

    def _fix(
        self, message: str, detail: str, edit: _Edit, *, kind: FindingKind = 'stale'
    ) -> None:
        self._find(kind, message, detail, fixed=True)
        self.edits.append(edit)

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
