"""What a citation of each kind says — glyph, link text, fragment, summary —
and which scenarios, tags, stories and terms a report holds to cite."""

import html
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import Literal, Self
from urllib.parse import quote

from ..model import (
    STATUSES,
    GlossaryTerm,
    Narration,
    NodeId,
    ReportData,
    Scenario,
    StoryId,
    TermId,
    build_term_crossrefs,
    rolled_up_status,
    scenario_identity,
)
from .coverage import build_coverage_map
from .glyphs import CITATION_GLYPH, CitationState
from .link_text import html_link_text, link_text
from .story_view import scenarios_by_story

type TargetKind = Literal['scenario', 'tag', 'story', 'term']

# A rollup citation's summary is built of these, and read back by them.
SUMMARY_SEPARATOR = ' · '
NO_SCENARIOS_SUMMARY = '(no scenarios)'

_TAG_SEPARATOR = '/'


@dataclass(frozen=True)
class Target:
    """What a report link's fragment names: a scenario by node ID — or by
    slug, until `citations update` rewrites it — a tag, or a story or term by
    id."""

    kind: TargetKind
    key: str


@dataclass(frozen=True, kw_only=True)
class Citation:
    state: CitationState
    # A scenario's title keeps its pieces, so its link text keeps the spans
    # each plain-text piece renders; a tag's, story's or term's is literal.
    title: Narration | str
    fragment: str
    summary: str | None

    @property
    def glyph(self) -> str:
        return CITATION_GLYPH[self.state]

    @property
    def title_text(self) -> str:
        return self.title if isinstance(self.title, str) else self.title.text

    @property
    def html_link_text(self) -> str:
        return html_link_text(self.title)

    def template_row(self) -> list[str]:
        """What `citation_templates` leave to fill: glyph, fragment, title, the
        summary, and the HTML title. The last two are left out when empty or
        when the HTML title matches the Markdown one, which keeps a page citing
        thousands of targets small."""
        title = link_text(self.title)
        html_title = self.html_link_text
        summary = f' {self.summary}' if self.summary else ''
        row = [self.glyph, self.fragment, title, summary]
        if html_title != title:
            return [*row, html_title]
        return row if summary else row[:3]


type CitationTemplate = list[str]


def citation_templates(report_url: str) -> dict[str, CitationTemplate]:
    """Each form a citation is copied in, keyed by its copy menu entry, as
    literal text and slot names alternating, so a page carries the forms and
    the report URL once and each target only its `template_row`."""
    glyph, fragment, title, html_title, summary = (
        f'\0{slot}\0'
        for slot in ('glyph', 'fragment', 'title', 'html_title', 'summary')
    )
    # A `<details>` form's body stays empty for `citations update` to fill.
    details = (
        f'<details markdown="1">\n<summary>{glyph} '
        f'<a href="{html.escape(report_url)}#{fragment}">{html_title}</a>'
    )
    closing = '</summary>\n\n</details>'
    return {
        'citation': _SLOT.split(f'{glyph} [{title}]({report_url}#{fragment}){summary}'),
        'narrated': _SLOT.split(f'{details}{closing}'),
        'defining': _SLOT.split(f'{details}{summary}{closing}'),
    }


_SLOT = re.compile(r'\0(\w+)\0')


def report_fragment(target: Target) -> str:
    """The fragment naming `target`, readable for a typical node ID or tag:
    only what `URLSearchParams` and `parse_qs` could misread is encoded."""
    value = quote(target.key, safe='/:')
    match target.kind:
        case 'scenario':
            return f'scenario={value}'
        case 'tag':
            return f'tag={value}'
        case 'story':
            return f'view=stories&story={value}'
        case 'term':
            return f'view=glossary&term={value}'


class CitationIndex:
    """The scenarios, tags, stories and terms a report lets a document cite. All
    but the scenarios are built on first use: a report without a URL needs none."""

    def __init__(
        self,
        report: ReportData,
        story_scenarios: Mapping[StoryId, list[Scenario]],
        term_scenarios: Mapping[TermId, list[NodeId]],
    ) -> None:
        self._report = report
        self._story_scenarios = story_scenarios
        self._term_scenarios = term_scenarios
        self.scenarios = _citable_scenarios(report)

    @cached_property
    def tags(self) -> dict[str, list[Scenario]]:
        """Under a tag and each of its prefixes, as `app.js`'s `underPrefix`
        matches a `#tag=` link to the scenarios it opens."""
        tagged: dict[str, list[Scenario]] = {}
        for scenario in self._report.scenarios:
            tags = {prefix for tag in scenario.tags for prefix in _prefixes(tag)}
            for tag in tags:
                tagged.setdefault(tag, []).append(scenario)
        return dict(sorted(tagged.items()))

    @cached_property
    def stories(self) -> dict[StoryId, tuple[str, list[Scenario]]]:
        return {
            story.id: (story.title, self._story_scenarios[story.id])
            for story in self._report.stories
        }

    @cached_property
    def terms(self) -> dict[TermId, tuple[GlossaryTerm, list[Scenario]]]:
        """Each with the scenarios the Glossary view lists for it."""
        glossary = self._report.glossary
        by_id = {scenario.id: scenario for scenario in self._report.scenarios}
        return {
            term.id: (
                term,
                [by_id[node_id] for node_id in self._term_scenarios.get(term.id, [])],
            )
            for term in (glossary.terms if glossary is not None else [])
        }

    @classmethod
    def of(cls, report: ReportData) -> Self:
        """For a caller that has not built the coverage and cross-references
        already."""
        return cls(
            report,
            scenarios_by_story(report, build_coverage_map(report)),
            build_term_crossrefs(
                report.scenarios, report.glossary, report.stories
            ).term_scenarios,
        )

    def citation(self, target: Target) -> Citation:
        """What a citation of a resolved `target` says."""
        fragment = report_fragment(target)
        match target.kind:
            case 'scenario':
                scenario = self.scenarios[NodeId(target.key)]
                return Citation(
                    state=scenario.status,
                    title=scenario.narration,
                    fragment=fragment,
                    summary=None,
                )
            case 'tag':
                return _rollup(target.key, fragment, self.counted(target))
            case 'story':
                title, told = self.stories[StoryId(target.key)]
                return _rollup(title, fragment, told)
            case 'term':
                term, using = self.terms[TermId(target.key)]
                return _rollup(term.canonical, fragment, using)

    def counted(self, target: Target) -> list[Scenario]:
        """The scenarios a resolved `target` names: a scenario itself, or those
        a tag's, story's or term's summary counts."""
        match target.kind:
            case 'scenario':
                return [self.scenarios[NodeId(target.key)]]
            case 'tag':
                return self.tags[target.key]
            case 'story':
                return self.stories[StoryId(target.key)][1]
            case 'term':
                return self.terms[TermId(target.key)][1]

    def cited(self, target: Target) -> Scenario | GlossaryTerm:
        """The scenario or term a resolved `target` names, which a `<details>`
        citation's body shows."""
        assert target.kind in ('scenario', 'term')
        if target.kind == 'scenario':
            return self.scenarios[NodeId(target.key)]
        return self.terms[TermId(target.key)][0]


def _citable_scenarios(report: ReportData) -> dict[NodeId, Scenario]:
    """Each scenario under the node ID a citation names it by: a grouped one as
    a whole, by its base node ID, as its own `id` is its first case's. A title
    is fixed at decoration, so a test function groups into one scenario."""
    return {
        NodeId(scenario_identity(scenario)): scenario for scenario in report.scenarios
    }


def _rollup(title: str, fragment: str, scenarios: list[Scenario]) -> Citation:
    counts = Counter(scenario.status for scenario in scenarios)
    summary = SUMMARY_SEPARATOR.join(
        f'{counts[status]} {CITATION_GLYPH[status]}'
        for status in STATUSES
        if counts[status]
    )
    return Citation(
        state=rolled_up_status(counts),
        title=title,
        fragment=fragment,
        summary=f'({summary})' if summary else NO_SCENARIOS_SUMMARY,
    )


def _prefixes(tag: str) -> Iterable[str]:
    parts = tag.split(_TAG_SEPARATOR)
    return (_TAG_SEPARATOR.join(parts[: depth + 1]) for depth in range(len(parts)))
