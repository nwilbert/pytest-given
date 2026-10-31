"""The delta page's context (`report/delta_html.py`): the data its template and
`delta.js` read, never the markup."""

import dataclasses

from pytest_given.delta import DeltaInputs, build_delta
from pytest_given.model import (
    DeltaData,
    DeltaMetadata,
    DeltaSide,
    Glossary,
    ReportData,
    ScenarioDelta,
)
from pytest_given.report.delta_html import (
    ListedScenario,
    ReasonRow,
    delta_render_context,
    render_delta_html,
)
from tests.unit.delta.builders import meta, report, scn, term
from tests.unit.report.app_data import embedded_app_data


def _delta(before: ReportData, after: ReportData) -> DeltaData:
    return build_delta(
        DeltaInputs(
            before=before,
            after=after,
            plugin_version='0.1.0',
            timestamp='2026-01-02T00:00:00+00:00',
        )
    ).delta


def _listed(delta: DeltaData) -> list[ListedScenario]:
    listed = delta_render_context(delta)['listed']
    assert isinstance(listed, list)
    return listed


def test_a_removed_and_an_added_scenario_sharing_a_node_id_have_a_fragment_each():
    """Only a rename log pairs the old `test_x` elsewhere and leaves the new
    one unpaired, so the delta is built by hand."""
    side = DeltaSide(metadata=meta(), modules=('t',))
    delta = DeltaData(
        metadata=DeltaMetadata(
            before=side, after=side, plugin_version='0.1.0', timestamp='now'
        ),
        scenarios=(
            ScenarioDelta(change='removed', before=scn('t.py::test_x', 'Old')),
            ScenarioDelta(change='added', after=scn('t.py::test_x', 'New')),
        ),
    )
    assert [item.fragment for item in _listed(delta)] == [
        'scenario=removed-t/x',
        'scenario=t/x',
    ]
    app_data = embedded_app_data(render_delta_html(delta, source_link_template=None))
    assert [entry['id'] for entry in app_data['scenarios']] == ['removed-t/x', 't/x']
    assert app_data['scenario_slugs'] == {'removed-t/x': 'removed-t/x', 't/x': 't/x'}


def test_modules_are_marked_by_which_sides_have_them_and_a_moved_file_is_not():
    before = report(
        scn('a.py::test_moved', 'Moved, unchanged'),
        scn('gone.py::test_old', 'Old'),
        scn('both.py::test_pay', 'Pay'),
    )
    after = report(
        scn('b.py::test_moved', 'Moved, unchanged'),
        scn('new.py::test_new', 'New'),
        scn('both.py::test_pay', 'Pay by card'),
    )
    context = delta_render_context(_delta(before, after))
    assert context['module_changes'] == {
        'gone': 'removed',
        'new': 'added',
        'both': 'changed',
    }


def test_the_sidebar_counts_listed_scenarios_by_change_and_the_unchanged_ones():
    before = report(
        scn('t.py::test_same', 'Same'),
        scn('t.py::test_pay', 'Pay'),
        scn('t.py::test_gone', 'Gone'),
    )
    after = report(
        scn('t.py::test_same', 'Same'),
        scn('t.py::test_pay', 'Pay now'),
        scn('t.py::test_new', 'New'),
        scn('t.py::test_newer', 'Newer'),
    )
    context = delta_render_context(_delta(before, after))
    assert context['change_counts'] == {'added': 2, 'changed': 1, 'removed': 1}
    assert context['unchanged_count'] == 1


def test_a_search_matches_either_side_s_title_and_a_removed_tag() -> None:
    before = report(scn('t.py::test_pay', 'Pay at the desk', tags=['legacy']))
    after = report(scn('t.py::test_pay', 'Pay online'))
    data = embedded_app_data(render_delta_html(_delta(before, after), None))
    [entry] = data['scenarios']
    assert entry['search_text'] == 'Pay at the desk Pay online legacy'
    assert (entry['change'], entry['tags']) == ('changed', [])


def test_a_changed_reason_keeps_the_one_it_replaced() -> None:
    def skipped(reason: str):
        return dataclasses.replace(
            scn('t.py::test_pay', 'Pay', status='skipped'), skip_reason=reason
        )

    before = report(skipped('no card reader'))
    after = report(skipped('no network'))
    [item] = _listed(_delta(before, after))
    assert item.reasons == [
        ReasonRow('skipped', 'Skipped:', 'no network', was='no card reader')
    ]


def test_a_reason_the_after_side_dropped_is_kept_as_what_it_was() -> None:
    before = report(
        dataclasses.replace(
            scn('t.py::test_pay', 'Pay', status='xfailed'), xfail_reason='bug 12'
        )
    )
    after = report(scn('t.py::test_pay', 'Pay', status='failed'))
    [item] = _listed(_delta(before, after))
    assert item.reasons == [
        ReasonRow('xfailed', 'Expected to fail:', None, was='bug 12')
    ]


def test_the_tooltip_knows_both_glossaries_terms_the_after_one_first() -> None:
    before = report(
        glossary=Glossary(terms=[term('room', 'Room'), term('guest', 'Guest')])
    )
    after = report(
        scn('t.py::test_new', 'New'),
        glossary=Glossary(terms=[term('guest', 'Visitor')]),
    )
    data = embedded_app_data(render_delta_html(_delta(before, after), None))
    assert [
        (entry['id'], entry['canonical']) for entry in data['glossary']['terms']
    ] == [('guest', 'Visitor'), ('room', 'Room')]
