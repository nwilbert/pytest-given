"""Rendering the delta HTML: the page's context and the filters it reads.

Each listed scenario and term renders against its own side: its term refs
resolve in that side's glossary, and its source link names that side's commit.
"""

# A CLI command that renders no HTML never loads Jinja or MarkupSafe.
__lazy_modules__ = ['jinja2', 'markupsafe']

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import jinja2
from markupsafe import Markup

from ..model import (
    AttachmentRef,
    CasePair,
    Change,
    ColumnId,
    DeltaData,
    DeltaSide,
    DiffSegment,
    Glossary,
    GlossaryTerm,
    Mark,
    Narration,
    NarrationPart,
    NarrationPlaceholder,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterDelta,
    ParameterTable,
    ReportData,
    Scenario,
    ScenarioDelta,
    SourceLocation,
    Step,
    TermDelta,
    TermFacts,
    TermId,
    build_term_crossrefs,
    narration_text,
    plural,
)
from .delta_steps import BlockKey, Side, StepsView, block_keys, steps_view
from .glossary_view import KindGrouping, group_by_kind
from .html_renderer import (
    base_env,
    build_param_color_map,
    bundled_assets,
    column_phase_blocks,
    make_narration_filter,
    make_source_url_filter,
    script_json_parse,
    shown_text,
    term_app_data,
)
from .inline_markdown import render_definition
from .slugs import build_scenario_slug_index
from .text import STATUS_LABEL
from .theme import DEFAULT_THEME, Theme

_SHORT_SHA = 7
# The Change filter's order: what a release brings, then what it took away.
_CHANGE_ORDER: tuple[Change, ...] = ('added', 'changed', 'removed')
# How a change is marked beside its word, wherever colour is not enough.
_CHANGE_GLYPH: dict[Change, str] = {
    'added': '+',
    'changed': '~',
    'removed': '\N{MINUS SIGN}',
}

type ColumnChange = Literal['added', 'removed']
type FormChange = Literal['added', 'removed']

# Prefixes a column only the before side has, where the page keys it: the after
# side can hold another column of the same ID.
_BEFORE_ONLY_KEY = 'before:'


@dataclass(frozen=True)
class ReasonRow:
    """A skip or xfail reason as the row shows it, with the before side's
    reason it replaced, if any."""

    status: Literal['skipped', 'xfailed']
    label: str
    reason: str | None
    was: str | None


@dataclass(frozen=True)
class TableColumn:
    column: ParameterColumn
    # A column only this side's table has. Attachment columns stay unmarked.
    change: ColumnChange | None = None
    was: str | None = None  # a renamed column's before name, on the after side


@dataclass(frozen=True)
class TableSide:
    side: Side
    parameters: ParameterTable
    columns: list[TableColumn]
    # Each column's phase block, keyed as the side's steps key theirs.
    column_blocks: dict[ColumnId, BlockKey]


@dataclass(frozen=True)
class TableRow:
    """A case's line across the tables, None on a side without the case."""

    before_case: ParameterCase | None
    after_case: ParameterCase | None
    pair: CasePair

    @property
    def change(self) -> Change | None:
        if self.before_case is None:
            return 'added'
        if self.after_case is None:
            return 'removed'
        pair = self.pair
        changed = pair.changed_cells or pair.id_changed or pair.status_changed
        return 'changed' if changed else None

    def case(self, side: Side) -> ParameterCase | None:
        return self.before_case if side == 'before' else self.after_case


@dataclass(frozen=True)
class TableView:
    """A changed scenario's parameter tables: a side for each table there is,
    the rows lined up by case in the after order."""

    sides: list[TableSide]
    rows: list[TableRow]


@dataclass(frozen=True)
class ListedScenario:
    # A changed scenario's before side carries its columns as the page keys
    # them (`_BeforeKeys`).
    delta: ScenarioDelta
    # Prefixed `removed-` for a removed scenario, so a removed and an added
    # scenario sharing one node ID still have a slug each.
    slug: str

    @property
    def change(self) -> Change:
        return self.delta.change

    @property
    def side(self) -> Side:
        """The side shown: after, or before for a removed scenario."""
        return 'before' if self.delta.after is None else 'after'

    @property
    def shown(self) -> Scenario:
        shown = self.delta.after or self.delta.before
        assert shown is not None
        return shown

    @property
    def fragment(self) -> str:
        return f'scenario={self.slug}'

    @property
    def title_text(self) -> str:
        return shown_text(self.shown.narration)

    @property
    def steps(self) -> StepsView | None:
        """A changed scenario's steps side by side; None for an added or
        removed one, whose steps read unmarked."""
        if self.change != 'changed':
            return None
        return steps_view(self.delta)

    @property
    def table(self) -> TableView | None:
        """A changed scenario's tables when they changed; None where a table
        reads unmarked, as in the report, or there is none."""
        if self.change != 'changed':
            return None
        return _table_view(self.delta)

    @property
    def reasons(self) -> list[ReasonRow]:
        replaced = self.delta.before if self.delta.reason_changed else None
        rows = [
            _reason_row(
                'skipped',
                'Skipped:',
                self.shown.skip_reason,
                replaced.skip_reason if replaced else None,
            ),
            _reason_row(
                'xfailed',
                'Expected to fail:',
                self.shown.xfail_reason,
                replaced.xfail_reason if replaced else None,
            ),
        ]
        return [row for row in rows if row.reason or row.was]


@dataclass(frozen=True)
class OtherForm:
    text: str
    change: FormChange | None = None


@dataclass(frozen=True)
class ListedTerm:
    """A term's card, shown from its after side, or its before side when it
    was removed."""

    delta: TermDelta
    # The listed scenarios that refer to it, on either side. Its unchanged
    # ones it only counts: they aren't on the page.
    scenarios: list[ListedScenario]

    @property
    def change(self) -> Change:
        return self.delta.change

    @property
    def side(self) -> Side:
        return 'before' if self.delta.after is None else 'after'

    @property
    def shown(self) -> GlossaryTerm:
        shown = self.delta.after or self.delta.before
        assert shown is not None
        return shown

    @property
    def key(self) -> str:
        """Its card's ID, prefixed `removed-` as a removed scenario's slug is:
        a term whose kind changed has a card under each kind."""
        prefix = 'removed-' if self.delta.after is None else ''
        return prefix + self.shown.id

    @property
    def was(self) -> str | None:
        """A renamed term's before name."""
        before, after = self.delta.before, self.delta.after
        if before is None or after is None or before.canonical == after.canonical:
            return None
        return before.canonical

    @property
    def other_forms(self) -> list[OtherForm]:
        shown = self._facts(self.side).other_forms
        if self.change != 'changed':
            return [OtherForm(form) for form in shown]
        before = self._facts('before').other_forms
        return [
            OtherForm(form, None if form in before else 'added') for form in shown
        ] + [OtherForm(form, 'removed') for form in before if form not in shown]

    @property
    def summary(self) -> tuple[str, ...]:
        """Its counts, a changed scenario count as `5 → 7 scenarios`."""
        facts = self._facts(self.side)
        scenarios = _some(facts.scenario_count, 'scenario')
        if self.change == 'changed':
            before_count = self._facts('before').scenario_count
            if before_count != facts.scenario_count:
                scenarios = f'{before_count} → {scenarios or "0 scenarios"}'
        parts = (_some(len(facts.other_forms), 'other form'), scenarios)
        return tuple(part for part in parts if part)

    @property
    def search_text(self) -> str:
        sides = (self.delta.before, self.delta.after)
        names = [side.canonical for side in sides if side is not None]
        return ' '.join(dict.fromkeys(names)).lower()

    def _facts(self, side: Side) -> TermFacts:
        facts = self.delta.before_facts if side == 'before' else self.delta.after_facts
        return facts or TermFacts()


@dataclass(frozen=True)
class DeltaGlossaryView:
    listed: list[ListedTerm]
    grouping: KindGrouping[ListedTerm]
    change_counts: dict[Change, int]
    unchanged_count: int
    undefined_count: int


def render_delta_html(
    delta: DeltaData,
    source_link_template: str | None,
    theme: Theme = DEFAULT_THEME,
) -> str:
    context = delta_render_context(delta, theme)
    env = _build_env(delta, source_link_template)
    return env.get_template('delta.html.j2').render(**context)


def delta_render_context(
    delta: DeltaData, theme: Theme = DEFAULT_THEME
) -> dict[str, object]:
    after = delta.metadata.after.metadata
    listed = _listed_scenarios(delta)
    module_changes = _module_changes(delta, listed)
    reach = _term_reach(delta, listed)
    glossary_view = _glossary_view(delta, listed, reach)
    side_labels: dict[Side, str] = {
        'before': range_label(delta.metadata.before),
        'after': range_label(delta.metadata.after),
    }
    return {
        'title': after.title or after.project,
        'range': f'{side_labels["before"]} to {side_labels["after"]}',
        'side_labels': side_labels,
        'listed': listed,
        'change_counts': {
            change: sum(item.change == change for item in listed)
            for change in _CHANGE_ORDER
        },
        'unchanged_count': len(delta.unchanged),
        'module_changes': module_changes,
        'glossary_view': glossary_view,
        # Browse by offers Terms as the report does, whenever a side has any.
        'browse_terms': bool(_tip_terms(delta)),
        'change_glyph': _CHANGE_GLYPH,
        'theme_default': theme,
        # Parameter coloring is off on this page: green, red and amber mean
        # only added, removed and changed.
        'param_colors': [],
        'app_data_js': script_json_parse(
            _app_data(delta, listed, module_changes, reach, glossary_view)
        ),
        **bundled_assets(),
    }


def range_label(side: DeltaSide) -> str:
    """The side's label and short SHA; the report's timestamp stands in for a
    SHA it doesn't carry."""
    sha = side.metadata.commit_sha
    when = sha[:_SHORT_SHA] if sha else side.metadata.timestamp
    return f'{side.label} {when}' if side.label else when


def _listed_scenarios(delta: DeltaData) -> list[ListedScenario]:
    # Slugged per side, each from the scenarios it shows.
    before_slugs = _slugs(
        delta.metadata.before,
        [_removed(listed) for listed in delta.scenarios if listed.after is None],
    )
    after_slugs = _slugs(
        delta.metadata.after,
        [listed.after for listed in delta.scenarios if listed.after is not None],
    )
    return [
        ListedScenario(
            _keyed(listed),
            after_slugs[listed.after.id]
            if listed.after is not None
            else 'removed-' + before_slugs[_removed(listed).id],
        )
        for listed in delta.scenarios
    ]


def _slugs(side: DeltaSide, scenarios: list[Scenario]) -> dict[NodeId, str]:
    return build_scenario_slug_index(
        ReportData(metadata=side.metadata, scenarios=scenarios)
    )


def _removed(scenario_delta: ScenarioDelta) -> Scenario:
    assert scenario_delta.before is not None
    return scenario_delta.before


def _table_view(scenario_delta: ScenarioDelta) -> TableView | None:
    before, after = scenario_delta.before, scenario_delta.after
    assert before is not None
    assert after is not None
    keys = block_keys(scenario_delta)
    parameters = scenario_delta.parameters
    if parameters is None:
        return _lone_table(before, after, keys)
    if not parameters.changed:
        return None
    assert before.parameters is not None
    assert after.parameters is not None
    removed = {pair.before for pair in parameters.columns if pair.after is None}
    added = {pair.after for pair in parameters.columns if pair.before is None}
    before_names = {column.id: column.name for column in before.parameters.columns}
    after_names = {column.id: column.name for column in after.parameters.columns}
    renamed_from = {
        pair.after: before_names[pair.before]
        for pair in parameters.columns
        if pair.paired_by == 'values'
        and pair.before is not None
        and pair.after is not None
        and before_names[pair.before] != after_names[pair.after]
    }
    before_cases = {case.id: case for case in before.parameters.cases}
    after_cases = {case.id: case for case in after.parameters.cases}
    return TableView(
        sides=[
            TableSide(
                'before',
                before.parameters,
                [
                    TableColumn(column, 'removed' if column.id in removed else None)
                    for column in before.parameters.columns
                ],
                _column_blocks(before, keys['before']),
            ),
            TableSide(
                'after',
                after.parameters,
                [
                    TableColumn(
                        column,
                        'added' if column.id in added else None,
                        renamed_from.get(column.id),
                    )
                    for column in after.parameters.columns
                ],
                _column_blocks(after, keys['after']),
            ),
        ],
        rows=[
            TableRow(
                before_cases[pair.before] if pair.before is not None else None,
                after_cases[pair.after] if pair.after is not None else None,
                pair,
            )
            for pair in parameters.cases
        ],
    )


def _lone_table(
    before: Scenario, after: Scenario, keys: dict[Side, list[BlockKey]]
) -> TableView | None:
    """The one table a scenario gained or lost with its parametrization, every
    case of it added or removed."""
    if before.parameters is not None:
        return TableView(
            [_unmarked_side('before', before, keys['before'])],
            [
                TableRow(case, None, CasePair(before=case.id))
                for case in before.parameters.cases
            ],
        )
    if after.parameters is not None:
        return TableView(
            [_unmarked_side('after', after, keys['after'])],
            [
                TableRow(None, case, CasePair(after=case.id))
                for case in after.parameters.cases
            ],
        )
    return None


def _unmarked_side(side: Side, scenario: Scenario, keys: list[BlockKey]) -> TableSide:
    table = scenario.parameters
    assert table is not None
    return TableSide(
        side,
        table,
        [TableColumn(column) for column in table.columns],
        _column_blocks(scenario, keys),
    )


def _column_blocks(
    scenario: Scenario, keys: list[BlockKey]
) -> dict[ColumnId, BlockKey]:
    return {
        column: keys[block] for column, block in column_phase_blocks(scenario).items()
    }


def _keyed(scenario_delta: ScenarioDelta) -> ScenarioDelta:
    if scenario_delta.change != 'changed':
        return scenario_delta
    columns = scenario_delta.parameters.columns if scenario_delta.parameters else ()
    keys = _BeforeKeys(
        {
            pair.before: pair.after
            for pair in columns
            if pair.before is not None and pair.after is not None
        }
    )
    return keys.scenario_delta(scenario_delta)


@dataclass(frozen=True)
class _BeforeKeys:
    """A changed scenario's before column IDs as the page keys them: a paired
    column's after ID, so a placeholder on either side finds its column in
    both tables, any other prefixed `before:`. `data-param` carries the key."""

    paired: dict[ColumnId, ColumnId]

    def scenario_delta(self, scenario_delta: ScenarioDelta) -> ScenarioDelta:
        before = scenario_delta.before
        assert before is not None
        return dataclasses.replace(
            scenario_delta,
            before=dataclasses.replace(
                before,
                narration=self._narration(before.narration),
                steps=[self._step(step) for step in before.steps],
                parameters=self._table(before.parameters),
            ),
            parameters=self._parameter_delta(scenario_delta.parameters),
        )

    def _key(self, column_id: ColumnId) -> ColumnId:
        return self.paired.get(column_id) or ColumnId(_BEFORE_ONLY_KEY + column_id)

    def _parts(self, parts: tuple[NarrationPart, ...]) -> tuple[NarrationPart, ...]:
        return tuple(
            dataclasses.replace(part, column_id=self._key(part.column_id))
            if isinstance(part, NarrationPlaceholder)
            else part
            for part in parts
        )

    def _narration(self, narration: Narration) -> Narration:
        return dataclasses.replace(narration, parts=self._parts(narration.parts))

    def _step(self, step: Step) -> Step:
        return dataclasses.replace(
            step,
            narration=self._narration(step.narration),
            children=[self._step(child) for child in step.children],
            attachments=[
                dataclasses.replace(
                    attachment, column_id=self._key(attachment.column_id)
                )
                if isinstance(attachment, AttachmentRef)
                else attachment
                for attachment in step.attachments
            ],
        )

    def _table(self, table: ParameterTable | None) -> ParameterTable | None:
        if table is None:
            return None
        return dataclasses.replace(
            table,
            columns=[
                dataclasses.replace(column, id=self._key(column.id))
                for column in table.columns
            ],
        )

    def _parameter_delta(
        self, parameters: ParameterDelta | None
    ) -> ParameterDelta | None:
        if parameters is None:
            return None
        return dataclasses.replace(
            parameters,
            columns=tuple(
                dataclasses.replace(pair, before=self._key(pair.before))
                if pair.before is not None
                else pair
                for pair in parameters.columns
            ),
        )


# The listed scenarios that refer to a term, by the side they were read on.
type TermReach = dict[Side, dict[TermId, list[ListedScenario]]]


def _term_reach(delta: DeltaData, listed: list[ListedScenario]) -> TermReach:
    sides: tuple[tuple[Side, DeltaSide, Glossary | None], ...] = (
        ('before', delta.metadata.before, delta.glossary.before),
        ('after', delta.metadata.after, delta.glossary.after),
    )
    reach: TermReach = {}
    for side, side_of, glossary in sides:
        read = {
            scenario.id: (scenario, item)
            for item in listed
            if (scenario := _on_side(item.delta, side)) is not None
        }
        crossrefs = build_term_crossrefs(
            ReportData(
                metadata=side_of.metadata,
                scenarios=[scenario for scenario, _ in read.values()],
                glossary=glossary,
            )
        )
        reach[side] = {
            term_id: [read[node_id][1] for node_id in node_ids]
            for term_id, node_ids in crossrefs.term_scenarios.items()
        }
    return reach


def _on_side(scenario_delta: ScenarioDelta, side: Side) -> Scenario | None:
    return scenario_delta.before if side == 'before' else scenario_delta.after


def _glossary_view(
    delta: DeltaData, listed: list[ListedScenario], reach: TermReach
) -> DeltaGlossaryView:
    cards = [
        ListedTerm(term_delta, _referring(term_delta, listed, reach))
        for term_delta in delta.glossary.terms
    ]
    return DeltaGlossaryView(
        listed=cards,
        grouping=group_by_kind(cards, lambda card: card.shown.kind),
        change_counts={
            change: sum(card.change == change for card in cards)
            for change in _CHANGE_ORDER
        },
        unchanged_count=len(delta.glossary.unchanged),
        undefined_count=sum(card.shown.definition is None for card in cards),
    )


def _referring(
    term_delta: TermDelta, listed: list[ListedScenario], reach: TermReach
) -> list[ListedScenario]:
    """In the list's order, each scenario once."""
    sides: tuple[tuple[Side, GlossaryTerm | None], ...] = (
        ('before', term_delta.before),
        ('after', term_delta.after),
    )
    slugs = {
        item.slug
        for side, term in sides
        if term is not None
        for item in reach[side].get(term.id, [])
    }
    return [item for item in listed if item.slug in slugs]


def _module_changes(
    delta: DeltaData, listed: list[ListedScenario]
) -> dict[str, Change]:
    """Each listed scenario's module, by which sides have it at all."""
    before = set(delta.metadata.before.modules)
    after = set(delta.metadata.after.modules)
    changes: dict[str, Change] = {}
    for item in listed:
        module = item.shown.module
        if module in before and module in after:
            changes[module] = 'changed'
        else:
            changes[module] = 'removed' if module in before else 'added'
    return changes


def _reason_row(
    status: Literal['skipped', 'xfailed'],
    label: str,
    reason: str | None,
    replaced: str | None,
) -> ReasonRow:
    return ReasonRow(status, label, reason, replaced if replaced != reason else None)


def _app_data(
    delta: DeltaData,
    listed: list[ListedScenario],
    module_changes: dict[str, Change],
    reach: TermReach,
    glossary_view: DeltaGlossaryView,
) -> dict[str, object]:
    """What `delta.js` seeds `reportApp()` with: the report's projection, one
    entry per listed scenario keyed by its slug, since a removed and an added
    scenario can share a node ID, and one per term card, keyed likewise."""
    return {
        'metadata': {'timestamp': delta.metadata.after.metadata.timestamp},
        'status_labels': STATUS_LABEL,
        'glossary': {'terms': [term_app_data(term) for term in _tip_terms(delta)]},
        'before_terms': [term_app_data(term) for term in _before_tip_terms(delta)],
        'term_ids': [card.key for card in glossary_view.listed],
        'term_cards': [
            {
                'key': card.key,
                'kind': card.shown.kind or 'kindless',
                'change': card.change,
                'defined': card.shown.definition is not None,
                'search': card.search_text,
                'before': card.delta.before.id if card.delta.before else None,
                'after': card.delta.after.id if card.delta.after else None,
            }
            for card in glossary_view.listed
        ],
        'term_scenarios': _shown_term_scenarios(reach),
        'scenarios': [
            {
                'id': item.slug,
                'module': item.shown.module,
                'tags': item.shown.tags,
                'status': item.shown.status,
                'change': item.change,
                'search_text': _search_text(item),
            }
            for item in listed
        ],
        'scenario_slugs': {item.slug: item.slug for item in listed},
        'module_changes': module_changes,
        'change_glyphs': _CHANGE_GLYPH,
    }


def _search_text(item: ListedScenario) -> str:
    """Both sides' titles, and the tags only the before side had."""
    sides = (item.delta.before, item.delta.after)
    titles = [shown_text(side.narration) for side in sides if side is not None]
    return ' '.join([*titles, *item.delta.tags_removed])


def _some(count: int, singular: str) -> str:
    """Empty for none, as the report's term summary lists only what it has."""
    return plural(count, singular) if count else ''


def _shown_term_scenarios(reach: TermReach) -> dict[TermId, list[str]]:
    """The Terms axis: each listed scenario under the terms of the side it is
    shown from."""
    shown: dict[TermId, list[str]] = {}
    for side, by_term in reach.items():
        for term_id, items in by_term.items():
            slugs = [item.slug for item in items if item.side == side]
            if slugs:
                shown.setdefault(term_id, []).extend(slugs)
    return shown


def _terms(glossary: Glossary | None) -> list[GlossaryTerm]:
    return glossary.terms if glossary is not None else []


def _tip_terms(delta: DeltaData) -> list[GlossaryTerm]:
    """The after glossary's terms, then the before glossary's it lacks, which
    no after-side ref can name."""
    after = _terms(delta.glossary.after)
    after_ids = {term.id for term in after}
    return after + [
        term for term in _terms(delta.glossary.before) if term.id not in after_ids
    ]


def _before_tip_terms(delta: DeltaData) -> list[GlossaryTerm]:
    """The before glossary's terms whose tooltip reads otherwise than the after
    glossary's term of that ID: a term ref read from the before side looks here
    first."""
    after = {term.id: term for term in _terms(delta.glossary.after)}
    return [
        term
        for term in _terms(delta.glossary.before)
        if (shared := after.get(term.id)) is not None
        and (shared.canonical, shared.definition) != (term.canonical, term.definition)
    ]


def _build_env(
    delta: DeltaData, source_link_template: str | None
) -> jinja2.Environment:
    env = base_env()
    listed = _listed_scenarios(delta)
    # Both sides', so a removed step's placeholder finds its column; only the
    # keys are read, parameter coloring being off on this page.
    param_color_map = build_param_color_map(
        [
            scenario
            for item in delta.scenarios
            for scenario in (item.before, item.after)
            if scenario is not None
        ]
    )
    narration_filters = {
        'before': make_narration_filter(param_color_map, delta.glossary.before),
        'after': make_narration_filter(param_color_map, delta.glossary.after),
    }
    # Compiled only for a side some scenario or term is shown from, so a
    # `{sha}` template fails only when a link would need the SHA a side lacks.
    shown_sides = {item.side for item in listed} | {
        'before' if term_delta.after is None else 'after'
        for term_delta in delta.glossary.terms
    }
    source_url_filters = {
        side: _source_url_filter(source_link_template, side_of)
        for side, side_of in (
            ('before', delta.metadata.before),
            ('after', delta.metadata.after),
        )
        if side in shown_sides
    }

    def narration(value: Narration, side: Side) -> Markup:
        return narration_filters[side](value)

    def source_url(value: SourceLocation | None, side: Side) -> str | None:
        return source_url_filters[side](value)

    def narration_diff(words: tuple[DiffSegment, ...], side: Side) -> Markup:
        """A modified step's text on one side, its changed words marked."""
        return Markup('').join(
            _marked(
                segment.mark,
                narration(
                    Narration(text=narration_text(segment.parts), parts=segment.parts),
                    side,
                ),
            )
            for segment in words
        )

    def definition_diff(words: tuple[DiffSegment, ...]) -> Markup:
        """A changed definition's word diff. A segment holds whole spans, so
        each renders on its own."""
        return Markup('').join(
            _marked(
                segment.mark,
                Markup(render_definition(narration_text(segment.parts))),
            )
            for segment in words
        )

    def no_param_color(column: ParameterColumn) -> str:
        return ''

    env.filters['narration'] = narration
    env.filters['narration_diff'] = narration_diff
    env.filters['definition_diff'] = definition_diff
    env.filters['source_url'] = source_url
    env.filters['param_color_class'] = no_param_color
    return env


def _marked(mark: Mark, text: Markup) -> Markup:
    match mark:
        case 'equal':
            return text
        case 'removed':
            return Markup('<del class="delta-words">{}</del>').format(text)
        case 'added':
            return Markup('<ins class="delta-words">{}</ins>').format(text)


def _source_url_filter(
    template: str | None, side: DeltaSide
) -> Callable[[SourceLocation | None], str | None]:
    return make_source_url_filter(
        template=template,
        project=side.metadata.project,
        commit_sha=side.metadata.commit_sha,
        root=None,
    )
