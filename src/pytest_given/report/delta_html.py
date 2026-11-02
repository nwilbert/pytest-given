"""Rendering the delta HTML: the page's context and the filters it reads.

Each listed scenario and term renders against its own side: its term refs
resolve in that side's glossary, and its source link names that side's commit.
"""

# A CLI command that renders no HTML never loads Jinja or MarkupSafe.
__lazy_modules__ = ['jinja2', 'markupsafe']

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Literal

import jinja2
from markupsafe import Markup

from ..model import (
    CHANGES,
    SIDE_MARK,
    AttachmentRef,
    CasePair,
    Change,
    ColumnId,
    DeltaData,
    DeltaSide,
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
    Side,
    SourceLocation,
    Step,
    StepDelta,
    TermDelta,
    TermFacts,
    TermId,
    build_term_crossrefs,
    narration_of,
    narration_text,
    on_side,
    other_side,
    plural,
)
from .delta_steps import (
    BlockKey,
    MarkedRun,
    StepsView,
    block_keys,
    side_runs,
    steps_view,
)
from .glossary_view import KindGrouping, group_by_kind, plural_if_any
from .html_renderer import (
    base_env,
    bundled_assets,
    bundled_script,
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
        return 'changed' if self.pair.changed else None

    def case(self, side: Side) -> ParameterCase | None:
        return on_side(side, self.before_case, self.after_case)


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
        return self.delta.shown_side

    @property
    def shown(self) -> Scenario:
        return self.delta.shown

    @property
    def fragment(self) -> str:
        return f'scenario={self.slug}'

    @cached_property
    def title_text(self) -> str:
        return shown_text(self.shown.narration)

    @cached_property
    def steps(self) -> StepsView | None:
        """A changed scenario's steps side by side; None for an added or
        removed one, whose steps read unmarked."""
        if self.change != 'changed':
            return None
        return steps_view(self.delta, self._block_keys)

    @cached_property
    def table(self) -> TableView | None:
        """A changed scenario's tables when they changed; None where a table
        reads unmarked, as in the report, or there is none."""
        if self.change != 'changed':
            return None
        return _table_view(self.delta, self._block_keys)

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

    @cached_property
    def _block_keys(self) -> dict[Side, list[BlockKey]]:
        return block_keys(self.delta)


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
        return self.delta.shown_side

    @property
    def shown(self) -> GlossaryTerm:
        return self.delta.shown

    @property
    def key(self) -> str:
        """Its card's ID, prefixed `removed-` as a removed scenario's slug is:
        a term whose kind changed has a card under each kind."""
        prefix = 'removed-' if self.delta.after is None else ''
        return prefix + self.shown.id

    @property
    def renamed_from(self) -> str | None:
        """A changed term's before name, where its after one differs."""
        before, after = self.delta.before, self.delta.after
        if before is None or after is None or before.canonical == after.canonical:
            return None
        return before.canonical

    @property
    def sides(self) -> tuple[Side, ...]:
        """A changed term's two, or the one it is shown from."""
        return ('before', 'after') if self.change == 'changed' else (self.side,)

    def term(self, side: Side) -> GlossaryTerm:
        term = self.delta.on(side)
        assert term is not None
        return term

    def definition(self, side: Side) -> tuple[MarkedRun, ...]:
        """A changed definition on one side, the words only it has marked;
        empty where the definition reads unmarked."""
        return side_runs(self.delta.definition, side)

    def other_forms(self, side: Side) -> list[OtherForm]:
        """A changed term's forms only this side has are marked."""
        forms = self._facts(side).other_forms
        if self.change != 'changed':
            return [OtherForm(form) for form in forms]
        other = self._facts(other_side(side)).other_forms
        return [
            OtherForm(form, None if form in other else SIDE_MARK[side])
            for form in forms
        ]

    def scenario_count(self, side: Side) -> str:
        """A changed term's on both sides, a none included, so they compare."""
        count = self._facts(side).scenario_count
        if self.change == 'changed':
            return plural(count, 'scenario')
        return plural_if_any(count, 'scenario')

    @property
    def search_text(self) -> str:
        sides = (self.delta.before, self.delta.after)
        names = [side.canonical for side in sides if side is not None]
        return ' '.join(dict.fromkeys(names)).lower()

    def _facts(self, side: Side) -> TermFacts:
        facts = on_side(side, self.delta.before_facts, self.delta.after_facts)
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
    return {
        'title': after.title or after.project,
        'range': (
            f'{range_label(delta.metadata.before)} to '
            f'{range_label(delta.metadata.after)}'
        ),
        # The version that built the delta: each side's run has its own.
        'plugin_version': delta.metadata.plugin_version,
        'listed': listed,
        'change_counts': {
            change: sum(item.change == change for item in listed) for change in CHANGES
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
        'delta_js': bundled_script('delta.js'),
    }


def range_label(side: DeltaSide) -> str:
    """The side's label and short SHA; the report's timestamp, to the minute,
    stands in for a SHA it doesn't carry."""
    sha = side.metadata.commit_sha
    when = (
        sha[:_SHORT_SHA]
        if sha
        else f'{datetime.fromisoformat(side.metadata.timestamp):%Y-%m-%d %H:%M}'
    )
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


def _table_view(
    scenario_delta: ScenarioDelta, keys: dict[Side, list[BlockKey]]
) -> TableView | None:
    before, after = scenario_delta.before, scenario_delta.after
    assert before is not None
    assert after is not None
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
            steps=tuple(self._step_delta(step) for step in scenario_delta.steps),
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

    def _step_delta(self, step_delta: StepDelta) -> StepDelta:
        """A word diff's before parts, which the before side's text reads."""
        return dataclasses.replace(
            step_delta,
            words=tuple(
                dataclasses.replace(segment, before=self._parts(segment.before))
                for segment in step_delta.words
            ),
            children=tuple(self._step_delta(child) for child in step_delta.children),
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
            if (scenario := item.delta.on(side)) is not None
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


def _glossary_view(
    delta: DeltaData, listed: list[ListedScenario], reach: TermReach
) -> DeltaGlossaryView:
    position = {item.slug: index for index, item in enumerate(listed)}
    cards = [
        ListedTerm(term_delta, _referring(term_delta, listed, position, reach))
        for term_delta in delta.glossary.terms
    ]
    return DeltaGlossaryView(
        listed=cards,
        grouping=group_by_kind(cards, lambda card: card.shown.kind),
        change_counts={
            change: sum(card.change == change for card in cards) for change in CHANGES
        },
        unchanged_count=len(delta.glossary.unchanged),
        undefined_count=sum(card.shown.definition is None for card in cards),
    )


def _referring(
    term_delta: TermDelta,
    listed: list[ListedScenario],
    position: dict[str, int],
    reach: TermReach,
) -> list[ListedScenario]:
    """In the list's order, each scenario once."""
    sides: tuple[Side, ...] = ('before', 'after')
    found = {
        position[item.slug]
        for side in sides
        if (term := term_delta.on(side)) is not None
        for item in reach[side].get(term.id, [])
    }
    return [listed[index] for index in sorted(found)]


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
    # Parameter colouring is off on this page. A ref links only to a term the
    # Glossary tab lists: an unchanged one has no card to open.
    terms = delta.glossary.terms
    narration_filters = {
        'before': make_narration_filter(
            None,
            delta.glossary.before,
            term_side='before',
            linked_terms={term.before.id for term in terms if term.before},
        ),
        'after': make_narration_filter(
            None,
            delta.glossary.after,
            term_side='after',
            linked_terms={term.after.id for term in terms if term.after},
        ),
    }
    # Compiled only for a side some scenario or term is shown from, so a
    # `{sha}` template fails only when a link would need the SHA a side lacks.
    shown_sides = {item.shown_side for item in delta.scenarios} | {
        term_delta.shown_side for term_delta in delta.glossary.terms
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

    def narration_diff(words: tuple[MarkedRun, ...], side: Side) -> Markup:
        """A modified step's text on one side, its changed words marked. A run
        holds whole spans, so each renders on its own."""
        return Markup('').join(
            _marked(
                run.mark,
                narration(narration_of(run.parts), side),
            )
            for run in words
        )

    def definition_diff(words: tuple[MarkedRun, ...]) -> Markup:
        """A changed definition on one side, its changed words marked."""
        return Markup('').join(
            _marked(run.mark, Markup(render_definition(narration_text(run.parts))))
            for run in words
        )

    env.filters['narration'] = narration
    env.filters['narration_diff'] = narration_diff
    env.filters['definition_diff'] = definition_diff
    env.filters['source_url'] = source_url
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
