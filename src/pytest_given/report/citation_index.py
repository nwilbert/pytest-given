"""What a citation of each kind says — glyph, link text, fragment, summary —
and which scenarios, tags and stories a report holds to cite."""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import Literal, Self
from urllib.parse import quote

from ..model import (
    STATUSES,
    Narration,
    NodeId,
    ReportData,
    Scenario,
    StoryId,
    node_base,
    rolled_up_status,
)
from .coverage import build_coverage_map
from .link_text import html_link_text, link_text
from .md_renderer import narration_body_md
from .story_view import scenarios_by_story
from .text import CITATION_GLYPH, CitationState

type TargetKind = Literal['scenario', 'tag', 'story']

# A tag or story citation's summary is built of these, and read back by them.
SUMMARY_SEPARATOR = ' · '
NO_SCENARIOS_SUMMARY = '(no scenarios)'

_TAG_SEPARATOR = '/'


@dataclass(frozen=True)
class Target:
    """What a report link's fragment names: a scenario by node ID — or by
    slug, until `citations update` rewrites it — a tag, or a story by id."""

    kind: TargetKind
    key: str


@dataclass(frozen=True, kw_only=True)
class Citation:
    state: CitationState
    # A scenario's title keeps its pieces, so its link text keeps the spans
    # each plain-text piece renders; a tag or story title is literal.
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
        assert isinstance(self.title, Narration)
        return html_link_text(self.title)

    def markdown_halves(self) -> tuple[str, str]:
        """The one-line citation a copy button puts on the clipboard, either
        side of the report URL — which a page citing thousands of targets
        carries once."""
        summary = f' {self.summary}' if self.summary else ''
        return (
            f'{self.glyph} [{link_text(self.title)}](',
            f'#{self.fragment}){summary}',
        )

    def narrated_halves(self) -> tuple[str, str]:
        """The `<details>` block's text either side of the report URL, its
        body empty for `citations update` to fill."""
        return (
            f'<details markdown="1">\n<summary>{self.glyph} <a href="',
            f'#{self.fragment}">{self.html_link_text}</a></summary>\n\n</details>',
        )


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


class CitationIndex:
    """The scenarios, tags and stories a report lets a document cite. The tags
    and stories are built on first use: a report without a URL needs neither."""

    def __init__(
        self, report: ReportData, story_scenarios: Mapping[StoryId, list[Scenario]]
    ) -> None:
        self._report = report
        self._story_scenarios = story_scenarios
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

    @classmethod
    def of(cls, report: ReportData) -> Self:
        """For a caller that has not built the coverage already."""
        return cls(report, scenarios_by_story(report, build_coverage_map(report)))

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

    def narration(self, target: Target) -> str:
        """The Markdown body of a narrated citation of a scenario `target`."""
        assert target.kind == 'scenario'
        return narration_body_md(self.scenarios[NodeId(target.key)])

    def counted(self, target: Target) -> list[Scenario]:
        """The scenarios a resolved `target` names: a scenario itself, or those
        a tag's or story's summary counts."""
        match target.kind:
            case 'scenario':
                return [self.scenarios[NodeId(target.key)]]
            case 'tag':
                return self.tags[target.key]
            case 'story':
                return self.stories[StoryId(target.key)][1]


def _citable_scenarios(report: ReportData) -> dict[NodeId, Scenario]:
    """Each scenario under the node ID a citation names it by: a grouped one as
    a whole, by its base node ID, as its own `id` is its first case's. A title
    is fixed at decoration, so a test function groups into one scenario."""
    return {
        NodeId(node_base(scenario.id))
        if scenario.parameters is not None
        else scenario.id: scenario
        for scenario in report.scenarios
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
