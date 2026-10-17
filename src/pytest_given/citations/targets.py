"""A report link read back: the target its fragment names, and what the report
holds under that name."""

import difflib
from collections.abc import Iterable, Mapping
from functools import cached_property
from urllib.parse import parse_qsl

from ..markdown import fold_whitespace
from ..model import NodeId, ReportData, StoryId, node_base
from ..report import CitationIndex, Target, build_scenario_slug_index


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


class TargetResolver:
    """What the report holds under the name a link gives a target."""

    def __init__(self, report: ReportData) -> None:
        self.index = CitationIndex.of(report)
        cited_as = {
            scenario.id: cited for cited, scenario in self.index.scenarios.items()
        }
        self._by_slug = {
            slug: cited_as[node_id]
            for node_id, slug in build_scenario_slug_index(report).items()
        }
        self._by_title: dict[str, list[NodeId]] = {}
        for cited, scenario in self.index.scenarios.items():
            title = fold_whitespace(scenario.narration.text)
            self._by_title.setdefault(title, []).append(cited)

    def resolve(self, target: Target) -> Target | None:
        """The target as a current citation names it, or None when the report
        holds nothing it names."""
        match target.kind:
            case 'scenario':
                return self._resolve_scenario(target.key)
            case 'tag':
                return target if target.key in self.index.tags else None
            case 'story':
                return target if target.key in self.index.stories else None

    def scenarios_titled(self, title: str) -> list[NodeId]:
        return self._by_title.get(title, [])

    def suggestions(self, target: Target, link_title: str) -> list[str]:
        """The closest targets the report does hold, for a target it lacks —
        suggestions only: `citations update` never writes one."""
        match target.kind:
            case 'scenario':
                return _closest(
                    id_label='node ID',
                    key=target.key,
                    ids=self.index.scenarios,
                    title_label='scenario title',
                    title=link_title,
                    id_by_title=self._scenario_by_title,
                )
            case 'tag':
                return _labelled(
                    'closest tags',
                    difflib.get_close_matches(target.key, list(self.index.tags), n=3),
                )
            case 'story':
                return _closest(
                    id_label='story id',
                    key=target.key,
                    ids=self.index.stories,
                    title_label='story title',
                    title=link_title,
                    id_by_title=self._story_by_title,
                )

    @cached_property
    def _scenario_by_title(self) -> dict[str, NodeId]:
        return {title: cited[-1] for title, cited in self._by_title.items()}

    @cached_property
    def _story_by_title(self) -> dict[str, StoryId]:
        return {title: story_id for story_id, (title, _) in self.index.stories.items()}

    def _resolve_scenario(self, key: str) -> Target | None:
        if key in self.index.scenarios:
            return Target('scenario', key)
        if key in self._by_slug:
            return Target('scenario', self._by_slug[key])
        base = node_base(key)
        if base != key and base in self.index.scenarios:
            return Target('scenario', base)
        return None


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
