"""The delta sinks (`report/delta_sinks.py`) and the delta page's context."""

import dataclasses
import json
from pathlib import Path

import pytest

from pytest_given.delta import DeltaInputs, build_delta
from pytest_given.model import (
    DeltaData,
    Glossary,
    PytestGivenError,
    ReportData,
    SourceLocation,
    delta_from_dict,
    delta_to_dict,
)
from pytest_given.report import delta_sinks
from pytest_given.report.delta_html import (
    ListedScenario,
    delta_render_context,
    range_label,
    render_delta_html,
)
from pytest_given.report.delta_sinks import DeltaSinkConfig, emit_delta_sinks
from tests.unit.delta.builders import (
    lit,
    meta,
    narr,
    ph,
    ref,
    report,
    scn,
    table,
    term,
)


def _delta(
    before: ReportData,
    after: ReportData,
    *,
    before_label: str | None = None,
    after_label: str | None = None,
) -> DeltaData:
    return build_delta(
        DeltaInputs(
            before=before,
            after=after,
            before_label=before_label,
            after_label=after_label,
            plugin_version='0.1.0',
            timestamp='2026-01-02T00:00:00+00:00',
        )
    ).delta


def _listed(delta: DeltaData) -> list[ListedScenario]:
    listed = delta_render_context(delta)['listed']
    assert isinstance(listed, list)
    return listed


def test_identical_reports_list_no_scenario() -> None:
    same = report(scn('t.py::test_pay', 'Pay by card'))
    assert _listed(_delta(same, same)) == []


def test_a_listed_scenario_is_shown_from_its_after_side_or_its_before_side_if_removed():
    before = report(scn('t.py::test_pay', 'Pay'), scn('t.py::test_gone', 'Gone'))
    after = report(scn('t.py::test_pay', 'Pay now'), scn('t.py::test_new', 'New'))
    listed = _listed(_delta(before, after))
    assert sorted((item.change, item.side, item.scenario.id) for item in listed) == [
        ('added', 'after', 't.py::test_new'),
        ('changed', 'after', 't.py::test_pay'),
        ('removed', 'before', 't.py::test_gone'),
    ]


@pytest.mark.parametrize(
    ('label', 'sha', 'expected'),
    [
        ('v0.6.0', 'e4f5a6b7c8d9', 'v0.6.0 e4f5a6b'),
        (None, 'e4f5a6b7c8d9', 'e4f5a6b'),
        (None, None, '2026-01-01T00:00:00+00:00'),
        ('v0.6.0', None, 'v0.6.0 2026-01-01T00:00:00+00:00'),
    ],
)
def test_a_range_side_shows_its_label_and_short_sha_or_its_timestamp(
    label: str | None, sha: str | None, expected: str
) -> None:
    delta = _delta(report(sha=sha), report(sha=sha), before_label=label)
    assert range_label(delta.metadata.before) == expected


def test_the_header_shows_the_range_and_the_after_title() -> None:
    before = report(sha='a1b2c3d4')
    after = ReportData(metadata=meta('e4f5a6b7', title='Shop'), scenarios=[])
    context = delta_render_context(_delta(before, after, after_label='v2'))
    assert context['range'] == 'a1b2c3d to v2 e4f5a6b'
    assert context['title'] == 'Shop'


def test_without_a_title_the_header_shows_the_after_project() -> None:
    context = delta_render_context(_delta(report(), report()))
    assert context['title'] == 'project'


def test_hostile_titles_and_case_ids_survive_the_json_and_are_escaped_in_the_html(
    tmp_path: Path,
) -> None:
    hostile_id = 't.py::test_x[a]::-é]'
    delta = _delta(report(), report(scn(hostile_id, '<b>"x"</b>')))
    json_path, html_path = tmp_path / 'delta.json', tmp_path / 'delta.html'
    emit_delta_sinks(
        delta_to_dict(delta), DeltaSinkConfig(json_path=json_path, html_path=html_path)
    )
    reread = delta_from_dict(json.loads(json_path.read_text(encoding='utf-8')))
    [listed] = reread.scenarios
    assert listed.after is not None
    assert listed.after.id == hostile_id
    assert listed.after.narration == delta.scenarios[0].after.narration
    html = html_path.read_text(encoding='utf-8')
    assert '<b>' not in html
    assert '&lt;b&gt;' in html
    assert 'a]::-é' in html


def test_a_title_renders_its_term_refs_and_placeholders_against_its_own_side() -> None:
    """A removed scenario's term refs resolve in the before glossary, which
    the after one no longer holds."""
    before = report(
        scn('t.py::test_book', narr(lit('Book a '), ref('room', 'room'))),
        glossary=Glossary(terms=[term('room', 'Room')]),
    )
    after = report(
        scn(
            't.py::test_pay[1]',
            narr(lit('Pay '), ph('amount')),
            parameters=table([('amount', 'param')], ('t.py::test_pay[1]', [1])),
        )
    )
    html = render_delta_html(_delta(before, after), source_link_template=None)
    assert 'data-term-id="room"' in html
    assert 'data-param="amount"' in html


def test_a_source_link_points_at_the_shown_side_s_commit() -> None:
    gone = dataclasses.replace(
        scn('t.py::test_gone', 'Gone'), source=SourceLocation(relpath='t.py', line=3)
    )
    new = dataclasses.replace(
        scn('t.py::test_new', 'New'), source=SourceLocation(relpath='t.py', line=7)
    )
    html = render_delta_html(
        _delta(report(gone, sha='b' * 40), report(new, sha='a' * 40)),
        source_link_template='https://x/{sha}/{relpath}#{line}',
    )
    assert f'https://x/{"b" * 40}/t.py#3' in html
    assert f'https://x/{"a" * 40}/t.py#7' in html


def test_both_sinks_are_written(tmp_path: Path) -> None:
    json_path, html_path = tmp_path / 'out/delta.json', tmp_path / 'out/delta.html'
    written = emit_delta_sinks(
        delta_to_dict(_delta(report(), report())),
        DeltaSinkConfig(json_path=json_path, html_path=html_path),
    )
    assert [rendered.path for rendered in written] == [json_path, html_path]
    assert json_path.is_file()
    assert html_path.is_file()


@pytest.mark.parametrize(
    ('field', 'path'),
    [('json_path', Path('delta.html')), ('html_path', Path('test_x.py'))],
)
def test_a_delta_sink_path_that_cannot_be_its_file_is_refused(
    field: str, path: Path
) -> None:
    with pytest.raises(PytestGivenError, match='must end in'):
        DeltaSinkConfig(**{field: path})


def test_a_failed_render_writes_neither_sink_and_discards_the_stale_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_path, html_path = tmp_path / 'delta.json', tmp_path / 'delta.html'
    json_path.write_text('stale', encoding='utf-8')
    html_path.write_text('stale', encoding='utf-8')

    def refuse(*_args: object, **_kwargs: object) -> str:
        raise PytestGivenError('cannot render')

    monkeypatch.setattr(delta_sinks, 'render_delta_html', refuse)
    with pytest.raises(PytestGivenError, match='cannot render') as raised:
        emit_delta_sinks(
            delta_to_dict(_delta(report(), report())),
            DeltaSinkConfig(json_path=json_path, html_path=html_path),
        )
    assert f'Removed the previous {json_path}' in str(raised.value)
    assert list(tmp_path.iterdir()) == []


def test_an_unexpected_render_failure_still_discards_the_stale_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = tmp_path / 'delta.html'
    stale.write_text('stale', encoding='utf-8')

    def crash(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError('boom')

    monkeypatch.setattr(delta_sinks, 'render_delta_html', crash)
    with pytest.raises(RuntimeError, match='boom'):
        emit_delta_sinks(
            delta_to_dict(_delta(report(), report())),
            DeltaSinkConfig(html_path=stale),
        )
    assert not stale.exists()
