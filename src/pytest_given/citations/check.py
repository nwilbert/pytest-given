"""`check_citations` is the whole job — read every document, compute every
finding and edit, and only then write — so a document that cannot be read
leaves every file as it was.
"""

import bisect
import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from urllib.parse import SplitResult, unquote, urlsplit

from ..markdown import Span
from ..model import (
    NodeId,
    PytestGivenError,
    ReportData,
    ReportUrl,
    node_base,
)
from ..report import CITATION_GLYPH, STATUS_GLYPH, Target, write_all_or_none
from .details import LooseDetails, scan_details
from .link_checks import (
    CitationFinding,
    DetailsCheck,
    Edit,
    MarkdownCheck,
    ReportLink,
)
from .markdown_links import scan_links
from .targets import TargetResolver, target_label


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
    # A mistyped URL or path matches no link, and every link it misses would
    # otherwise read as current.
    if not links:
        raise PytestGivenError(
            f'No document links to the report at {location}: --report-url, or the '
            'URL the report stores, and --report-path must name where the '
            'documents link it.'
        )
    updated = [path for path, text in edited.items() if text != texts[path]]
    _write_documents({path: edited[path] for path in updated}, texts)
    return CitationsResult(
        links=links,
        listed=[link for link in links if covers(link.resolved)],
        updated=updated,
    )


def _write_documents(edited: dict[Path, str], read: dict[Path, str]) -> None:
    """Write every edited document or none, and none another writer saved
    since it was read: that save would be lost under the text analyzed."""

    def refuse_a_changed_document() -> None:
        changed = [path for path in edited if _read(path) != read[path]]
        if changed:
            raise PytestGivenError(
                f'{", ".join(path.as_posix() for path in changed)} changed while '
                'citations ran, so nothing was written; run the update again.'
            )

    # `newline=''`: an update rewrites no line ending it does not mean to.
    write_all_or_none(
        edited.items(), newline='', before_replace=refuse_a_changed_document
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

    def __str__(self) -> str:
        return ' or '.join(
            [
                *([] if self.url is None else [self.url.geturl()]),
                *([] if self.path is None else [self.path.as_posix()]),
            ]
        )

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
    it, or a tag — through its prefixes — story or term counting it. A link that
    resolves to nothing may be one under a name it no longer has."""

    def __init__(self, resolver: TargetResolver, covering: Sequence[str]) -> None:
        self._index = resolver.index
        self._ids: set[NodeId] = set()
        for node_id in covering:
            target = Target('scenario', node_id)
            resolved = resolver.resolve(target)
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
                            f'{target_label(target)} is not in the report',
                            *resolver.suggestions(target, ''),
                        ]
                    )
                )
            self._ids.update(scenario.id for scenario in scenarios)
        # A document links the same few tags, stories and terms, again and again.
        self._covers: dict[Target, bool] = {}

    def __call__(self, resolved: Target | None) -> bool:
        if not self._ids or resolved is None:
            return True
        if resolved not in self._covers:
            self._covers[resolved] = any(
                scenario.id in self._ids for scenario in self._index.counted(resolved)
            )
        return self._covers[resolved]


# Also read as a citation's glyph, and rewritten as emoji: the Markdown sink's
# glyphs and a typed `?`, so a hand-typed placeholder works either way.
_READ_GLYPHS = (*CITATION_GLYPH.values(), *STATUS_GLYPH.values(), '?')


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
) -> tuple[list[ReportLink], list[Edit]]:
    """A `<details>` citation of a scenario or term owns its body, rewritten
    whole, so nothing in it is read: neither a link nor another such citation."""
    edits: list[Edit] = []
    links: list[ReportLink] = []
    line_break = _first_line_break(text)
    # In document order, so an owned body is known before what it holds.
    owned: list[Span] = []

    def check(link_check: DetailsCheck | MarkdownCheck) -> None:
        fragment = _report_fragment(link_check.link.destination, path, location)
        if fragment is not None and (checked := link_check.run(fragment)) is not None:
            links.append(checked)

    for found in scan_details(text, _READ_GLYPHS):
        if isinstance(found, LooseDetails):
            fragment = _report_fragment(found.href, path, location)
            if fragment is not None and not _within(owned, found.offset):
                links.append(_mistyped_details(path, found, fragment))
        elif not _within(owned, found.opening_tag_span[0]):
            details = DetailsCheck(path, found, resolver, edits, line_break)
            check(details)
            if details.owns_body:
                owned.append(found.body_span)
    for link in scan_links(text, _READ_GLYPHS):
        if not _within(owned, link.text_span[0]):
            check(MarkdownCheck(path, link, resolver, edits))
    links.sort(key=lambda link: link.line)
    return links, edits


def _within(spans: list[Span], offset: int) -> bool:
    """Whether `offset` falls in one of `spans`, sorted and disjoint."""
    index = bisect.bisect_right(spans, offset, key=lambda span: span[0])
    return index > 0 and offset < spans[index - 1][1]


def _first_line_break(text: str) -> str:
    """What an update ends each line it writes with: the document's own."""
    end = text.find('\n')
    return '\r\n' if end > 0 and text[end - 1] == '\r' else '\n'


def _mistyped_details(path: Path, loose: LooseDetails, fragment: str) -> ReportLink:
    return ReportLink(
        path=path,
        line=loose.line,
        glyph=None,
        named=f'#{fragment}',
        resolved=None,
        findings=(
            CitationFinding(
                path=path,
                line=loose.line,
                kind='mistyped',
                message=f'a <details> block cites the report, but {loose.reason}',
                fixed_by_update=False,
            ),
        ),
    )


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


def _apply(text: str, edits: list[Edit]) -> str:
    ordered = sorted(edits)
    for edit, following in itertools.pairwise(ordered):
        assert edit.end <= following.start, (
            f'overlapping citation edits: {edit}, {following}'
        )
    for edit in reversed(ordered):
        text = text[: edit.start] + edit.text + text[edit.end :]
    return text
