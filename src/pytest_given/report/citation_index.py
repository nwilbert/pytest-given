"""What a citation of each kind says — glyph, link text, fragment, summary —
and which scenarios, tags and stories a report holds to cite."""

import difflib
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qsl, quote

from ..model import (
    STATUSES,
    NodeId,
    ReportData,
    Scenario,
    StoryId,
    node_base,
    rolled_up_status,
)
from .coverage import CoverageMap, build_coverage_map
from .link_text import fold_whitespace, link_text
from .slugs import build_scenario_slug_index
from .story_view import build_story_rollups
from .text import CITATION_GLYPH, CitationState

type TargetKind = Literal['scenario', 'tag', 'story']

TAG_SEPARATOR = '/'


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

    def markdown(self, report_url: str) -> str:
        """The one-line citation a copy button puts on the clipboard."""
        summary = f' {self.summary}' if self.summary else ''
        return (
            f'{self.glyph} [{link_text(self.title)}]'
            f'({report_url}#{self.fragment}){summary}'
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


def parse_fragment(fragment: str) -> Target | None:
    """The target a report link's fragment names, in any parameter order; None
    for any other fragment, which makes the link an ordinary one."""
    pairs = parse_qsl(fragment, keep_blank_values=True)
    params = dict(pairs)
    keys = sorted(key for key, _ in pairs)
    if keys == ['scenario']:
        return Target('scenario', params['scenario'])
    if keys == ['tag']:
        return Target('tag', params['tag'])
    if keys == ['story', 'view'] and params['view'] == 'stories':
        return Target('story', params['story'])
    return None


class CitationIndex:
    """The scenarios, tags and stories a report lets a document cite."""

    def __init__(self, report: ReportData, coverage: CoverageMap | None = None) -> None:
        self.scenarios = _citable_scenarios(report)
        cited_as = {scenario.id: cited for cited, scenario in self.scenarios.items()}
        self._by_slug = {
            slug: cited_as[node_id]
            for node_id, slug in build_scenario_slug_index(report).items()
        }
        # Under a tag and each of its prefixes, as `app.js`'s `underPrefix`
        # matches a `#tag=` link to the scenarios it opens.
        self._tagged: dict[str, list[Scenario]] = {}
        for scenario in report.scenarios:
            tags = {prefix for tag in scenario.tags for prefix in _prefixes(tag)}
            for tag in tags:
                self._tagged.setdefault(tag, []).append(scenario)
        self.tags = sorted(self._tagged)
        rollups = build_story_rollups(report, coverage or build_coverage_map(report))
        self._stories = {
            story.id: (story.title, rollups[story.id].scenarios)
            for story in report.stories
        }
        self.story_ids = list(self._stories)

    def resolve(self, target: Target) -> Target | None:
        """The target as a current citation names it, or None when the report
        holds nothing it names."""
        match target.kind:
            case 'scenario':
                return self._resolve_scenario(target.key)
            case 'tag':
                return target if target.key in self._tagged else None
            case 'story':
                return target if target.key in self._stories else None

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
                return _rollup(target.key, fragment, self._tagged[target.key])
            case 'story':
                title, told = self._stories[StoryId(target.key)]
                return _rollup(title, fragment, told)

    def scenarios_titled(self, title: str) -> list[NodeId]:
        return [
            cited
            for cited, scenario in self.scenarios.items()
            if fold_whitespace(scenario.narration.text) == title
        ]

    def suggestions(self, target: Target, link_title: str) -> list[str]:
        """The closest targets the report does hold, for a target it lacks —
        suggestions only: `citations update` never writes one."""
        match target.kind:
            case 'scenario':
                return _closest(
                    id_label='node id',
                    key=target.key,
                    ids=self.scenarios,
                    title_label='scenario title',
                    title=link_title,
                    id_by_title={
                        fold_whitespace(scenario.narration.text): cited
                        for cited, scenario in self.scenarios.items()
                    },
                )
            case 'tag':
                return _labelled(
                    'closest tags',
                    difflib.get_close_matches(target.key, self.tags, n=3),
                )
            case 'story':
                return _closest(
                    id_label='story id',
                    key=target.key,
                    ids=self._stories,
                    title_label='story title',
                    title=link_title,
                    id_by_title={
                        title: story_id
                        for story_id, (title, _) in self._stories.items()
                    },
                )

    def _resolve_scenario(self, key: str) -> Target | None:
        if key in self.scenarios:
            return Target('scenario', key)
        if key in self._by_slug:
            return Target('scenario', self._by_slug[key])
        base = node_base(key)
        if base != key and base in self.scenarios:
            return Target('scenario', base)
        return None


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
    summary = ' · '.join(
        f'{counts[status]} {CITATION_GLYPH[status]}'
        for status in STATUSES
        if counts[status]
    )
    return Citation(
        state=rolled_up_status(counts),
        title=title,
        fragment=fragment,
        summary=f'({summary})' if summary else '(no scenarios)',
    )


def _prefixes(tag: str) -> Iterable[str]:
    parts = tag.split(TAG_SEPARATOR)
    return (TAG_SEPARATOR.join(parts[: depth + 1]) for depth in range(len(parts)))


def _closest(
    *,
    id_label: str,
    key: str,
    ids: Iterable[str],
    title_label: str,
    title: str,
    id_by_title: Mapping[str, str],
) -> list[str]:
    return _labelled(
        f'closest by {id_label}',
        difflib.get_close_matches(key, ids, n=3),
    ) + _labelled(
        f'closest by {title_label}',
        [
            f'{id_by_title[matched]} ("{matched}")'
            for matched in difflib.get_close_matches(title, list(id_by_title), n=3)
        ],
    )


def _labelled(label: str, items: list[str]) -> list[str]:
    return [f'{label}: {", ".join(items)}'] if items else []
