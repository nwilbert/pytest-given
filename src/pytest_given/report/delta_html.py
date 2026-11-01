"""Rendering the delta HTML: the page's context and the filters it reads.

Each listed scenario renders against its own side: its term refs resolve in
that side's glossary, and its source link names that side's commit.
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
    Phase,
    ReportData,
    Scenario,
    ScenarioDelta,
    SourceLocation,
    Step,
    StepChange,
    StepDelta,
    StepPath,
    narration_text,
    walk_steps,
)
from .html_renderer import (
    base_env,
    build_param_color_map,
    bundled_assets,
    make_narration_filter,
    make_source_url_filter,
    phase_blocks,
    script_json_parse,
    shown_text,
    term_app_data,
)
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

type Side = Literal['before', 'after']
# Which glossary a text reads against, and whether a hovered row previews its
# values in it. `before` is a changed scenario's before text, which no row
# previews into: its placeholders share their keys with the after table's
# columns. `removed` is a removed scenario's, previewing from its own table.
type TextSide = Literal['before', 'after', 'removed']
type ColumnChange = Literal['added', 'removed']

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
class StepRow:
    """A step as a changed scenario reads it, from the side it comes from. An
    added or removed step stands for its whole subtree, so it has no rows
    below it."""

    change: StepChange
    side: Side
    step: Step
    words: tuple[DiffSegment, ...]
    was_phase: Phase | None
    children: tuple[StepRow, ...]


@dataclass(frozen=True)
class StepBlock:
    """A run of top-level rows under one keyword, as the report's phase
    blocks are, split also where a step's phase changed."""

    phase: Phase
    was_phase: Phase | None
    # The after scenario's phase block, which its parameter table's columns
    # name; None for a block of removed steps alone.
    after_block: int | None
    rows: list[StepRow]


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
    def text_side(self) -> TextSide:
        """How the shown scenario's own text, title and steps, renders."""
        return 'removed' if self.delta.after is None else 'after'

    @property
    def shown(self) -> Scenario:
        shown = self.delta.after or self.delta.before
        assert shown is not None
        return shown

    @property
    def fragment(self) -> str:
        return f'scenario={self.slug}'

    @property
    def step_blocks(self) -> list[StepBlock] | None:
        """A changed scenario's steps with their changes; None for an added or
        removed one, whose steps read unmarked."""
        if self.change != 'changed':
            return None
        return _step_blocks(self.delta)

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
        'change_glyph': _CHANGE_GLYPH,
        'theme_default': theme,
        # Parameter coloring is off on this page: green, red and amber mean
        # only added, removed and changed.
        'param_colors': [],
        'app_data_js': script_json_parse(_app_data(delta, listed, module_changes)),
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


def _step_blocks(scenario_delta: ScenarioDelta) -> list[StepBlock]:
    before, after = scenario_delta.before, scenario_delta.after
    assert before is not None
    assert after is not None
    rows = _StepRows(dict(walk_steps(before.steps)), dict(walk_steps(after.steps)))
    after_blocks = [
        index for index, block in enumerate(phase_blocks(after.steps)) for _ in block
    ]
    blocks: list[StepBlock] = []
    for step_delta in scenario_delta.steps:
        row = rows.row(step_delta)
        after_block = after_blocks[step_delta.after[0]] if step_delta.after else None
        last = blocks[-1] if blocks else None
        if last and (last.phase, last.was_phase) == (row.step.phase, row.was_phase):
            last.rows.append(row)
            if last.after_block is None:
                blocks[-1] = dataclasses.replace(last, after_block=after_block)
        else:
            blocks.append(StepBlock(row.step.phase, row.was_phase, after_block, [row]))
    return blocks


@dataclass(frozen=True)
class _StepRows:
    before: dict[StepPath, Step]
    after: dict[StepPath, Step]

    def row(self, step_delta: StepDelta) -> StepRow:
        side: Side = 'before' if step_delta.change == 'removed' else 'after'
        path = step_delta.before if side == 'before' else step_delta.after
        assert path is not None
        was_phase = None
        if step_delta.phase_changed:
            assert step_delta.before is not None
            was_phase = self.before[step_delta.before].phase
        return StepRow(
            change=step_delta.change,
            side=side,
            step=(self.before if side == 'before' else self.after)[path],
            words=step_delta.words,
            was_phase=was_phase,
            children=tuple(self.row(child) for child in step_delta.children),
        )


def _table_view(scenario_delta: ScenarioDelta) -> TableView | None:
    before, after = scenario_delta.before, scenario_delta.after
    assert before is not None
    assert after is not None
    parameters = scenario_delta.parameters
    if parameters is None:
        return _lone_table(before.parameters, after.parameters)
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
    before: ParameterTable | None, after: ParameterTable | None
) -> TableView | None:
    """The one table a scenario gained or lost with its parametrization, every
    case of it added or removed."""
    if before is not None:
        return TableView(
            [_unmarked_side('before', before)],
            [TableRow(case, None, CasePair(before=case.id)) for case in before.cases],
        )
    if after is not None:
        return TableView(
            [_unmarked_side('after', after)],
            [TableRow(None, case, CasePair(after=case.id)) for case in after.cases],
        )
    return None


def _unmarked_side(side: Side, table: ParameterTable) -> TableSide:
    return TableSide(side, table, [TableColumn(column) for column in table.columns])


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
        """Only removed words read from the before side."""
        return dataclasses.replace(
            step_delta,
            words=tuple(
                dataclasses.replace(segment, parts=self._parts(segment.parts))
                if segment.mark == 'removed'
                else segment
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
) -> dict[str, object]:
    """What `delta.js` seeds `reportApp()` with: the report's projection, one
    entry per listed scenario keyed by its slug, since a removed and an added
    scenario can share a node ID."""
    return {
        'metadata': {'timestamp': delta.metadata.after.metadata.timestamp},
        'status_labels': STATUS_LABEL,
        'glossary': {
            'terms': [term_app_data(term) for term in _terms(delta.glossary.after)]
        },
        'before_terms': [term_app_data(term) for term in _before_tip_terms(delta)],
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


def _terms(glossary: Glossary | None) -> list[GlossaryTerm]:
    return glossary.terms if glossary is not None else []


def _before_tip_terms(delta: DeltaData) -> list[GlossaryTerm]:
    """The before glossary's terms whose tooltip reads otherwise than the after
    glossary's term of that ID, or that it lacks: a term ref read from the
    before side looks here first."""
    after = {term.id: term for term in _terms(delta.glossary.after)}
    return [
        term
        for term in _terms(delta.glossary.before)
        if (shared := after.get(term.id)) is None
        or (shared.canonical, shared.definition) != (term.canonical, term.definition)
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
        side: make_narration_filter(
            param_color_map, glossary, substitutes=side != 'before'
        )
        for side, glossary in (
            ('before', delta.glossary.before),
            ('after', delta.glossary.after),
            ('removed', delta.glossary.before),
        )
    }
    # Compiled only for a side some scenario is shown from, so a `{sha}`
    # template fails only when a link would need the SHA a side lacks.
    shown_sides = {item.side for item in listed}
    source_url_filters = {
        side: _source_url_filter(source_link_template, side_of)
        for side, side_of in (
            ('before', delta.metadata.before),
            ('after', delta.metadata.after),
        )
        if side in shown_sides
    }

    def narration(value: Narration, side: TextSide) -> Markup:
        return narration_filters[side](value)

    def source_url(value: SourceLocation | None, side: Side) -> str | None:
        return source_url_filters[side](value)

    def narration_diff(words: tuple[DiffSegment, ...]) -> Markup:
        """A modified step's word diff: removed runs read from the before
        side, equal and added ones from the after side."""
        return Markup('').join(
            _marked(
                segment.mark,
                narration(
                    Narration(text=narration_text(segment.parts), parts=segment.parts),
                    'before' if segment.mark == 'removed' else 'after',
                ),
            )
            for segment in words
        )

    def no_param_color(column: ParameterColumn) -> str:
        return ''

    env.filters['narration'] = narration
    env.filters['narration_diff'] = narration_diff
    env.filters['source_url'] = source_url
    env.filters['param_color_class'] = no_param_color
    return env


def _marked(mark: Mark, text: Markup) -> Markup:
    match mark:
        case 'equal':
            return text
        case 'removed':
            return Markup(
                '<del class="delta-words" data-term-side="before">{}</del>'
            ).format(text)
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
