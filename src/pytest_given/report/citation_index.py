"""What a citation of each kind says — glyph, link text, fragment, summary —
and which scenarios, tags and stories a report holds to cite."""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, Self
from urllib.parse import quote

from ..model import (
    STATUSES,
    NodeId,
    ReportData,
    Scenario,
    StoryId,
    node_base,
    rolled_up_status,
)
from .coverage import build_coverage_map
from .link_text import link_text
from .story_view import scenarios_by_story
from .text import CITATION_GLYPH, CitationState

type TargetKind = Literal['scenario', 'tag', 'story']

# A tag or story citation's summary is built of these, and read back by them.
SUMMARY_SEPARATOR = ' · '
NO_SCENARIOS_SUMMARY = '(no scenarios)'

_TAG_SEPARATOR = '/'


@dataclass(frozen=True)
class Target:
    """What a report link's fragment names: a scenario by node id — or by
    slug, until `citations update` rewrites it — a tag, or a story by id."""

    kind: TargetKind
    key: str


@dataclass(frozen=True, kw_only=True)
class Citation:
    state: CitationState
    title: str
    fragment: str
    summary: str | None

    @property
    def glyph(self) -> str:
        return CITATION_GLYPH[self.state]

    def markdown_halves(self) -> tuple[str, str]:
        """The one-line citation a copy button puts on the clipboard, either
        side of the report URL — which a page citing thousands of targets
        carries once."""
        summary = f' {self.summary}' if self.summary else ''
        return (
            f'{self.glyph} [{link_text(self.title)}](',
            f'#{self.fragment}){summary}',
        )


def report_fragment(target: Target) -> str:
    """The fragment naming `target`, readable for a typical node id or tag:
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
    """The scenarios, tags and stories a report lets a document cite."""

    def __init__(
        self, report: ReportData, story_scenarios: Mapping[StoryId, list[Scenario]]
    ) -> None:
        self.scenarios = _citable_scenarios(report)
        # Under a tag and each of its prefixes, as `app.js`'s `underPrefix`
        # matches a `#tag=` link to the scenarios it opens.
        tagged: dict[str, list[Scenario]] = {}
        for scenario in report.scenarios:
            tags = {prefix for tag in scenario.tags for prefix in _prefixes(tag)}
            for tag in tags:
                tagged.setdefault(tag, []).append(scenario)
        self.tags = dict(sorted(tagged.items()))
        self.stories = {
            story.id: (story.title, story_scenarios[story.id])
            for story in report.stories
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
                    title=scenario.narration.text,
                    fragment=fragment,
                    summary=None,
                )
            case 'tag':
                return _rollup(target.key, fragment, self.tags[target.key])
            case 'story':
                title, told = self.stories[StoryId(target.key)]
                return _rollup(title, fragment, told)


def _citable_scenarios(report: ReportData) -> dict[NodeId, Scenario]:
    """Each scenario under the node id a citation names it by.

    A grouped scenario is cited as a whole, by its base node id: its own `id`
    is its first case's. Two groups of one function — a title differing per
    case — would share that base, so each keeps its own id instead.
    """
    grouped_bases = Counter(
        node_base(scenario.id)
        for scenario in report.scenarios
        if scenario.parameters is not None
    )
    cited: dict[NodeId, Scenario] = {}
    for scenario in report.scenarios:
        base = NodeId(node_base(scenario.id))
        alone = scenario.parameters is not None and grouped_bases[base] == 1
        cited[base if alone else scenario.id] = scenario
    return cited


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
