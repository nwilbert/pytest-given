"""Unit tests for the sink render/write/discard split (`report/sinks.py`)."""

import json
from pathlib import Path

import pytest

from pytest_given import PytestGivenError, given, scenario, then, when
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPart,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Metadata,
    Narration,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Step,
    Story,
    StoryId,
    TermId,
    report_to_dict,
)
from pytest_given.report import sinks
from pytest_given.report.sinks import SinkConfig, discard_stale_sinks
from tests.ubiquitous_language import pg


def test_discard_stale_sinks_removes_the_paths_this_run_would_have_written(
    tmp_path,
) -> None:
    stale = tmp_path / 'report.html'
    stale.write_text('previous run', encoding='utf-8')
    notes = discard_stale_sinks(SinkConfig(html_path=stale))
    assert not stale.exists()
    assert notes == [f'Removed the previous {stale} — it would read as current.']


def test_discard_stale_sinks_reports_an_unlink_failure_instead_of_raising(
    tmp_path, monkeypatch
) -> None:
    """The caller is already handling a failed write; the usual reason that
    write failed is also a reason the unlink will, and an exception here would
    escape `pytest_sessionfinish` as the bare traceback the handler exists to
    prevent."""
    stale = tmp_path / 'report.html'
    stale.write_text('previous run', encoding='utf-8')

    def refuse(self: Path, **kwargs: object) -> None:
        raise PermissionError('read-only file system')

    monkeypatch.setattr(Path, 'unlink', refuse)
    [note] = discard_stale_sinks(SinkConfig(html_path=stale))
    assert note == f'Could not remove the previous {stale}: read-only file system'


def test_a_sink_path_that_cannot_be_a_report_file_is_refused(tmp_path) -> None:
    """A bare `--given-html` consumes the next argument, so a mis-ordered
    invocation would otherwise aim the renderer at the user's own source file —
    and `discard_stale_sinks` would then unlink it as a stale report."""
    source = tmp_path / 'test_demo.py'
    source.write_text('def test_x(): pass', encoding='utf-8')
    with pytest.raises(PytestGivenError) as excinfo:
        SinkConfig(html_path=source)
    assert 'must end in .html or .htm' in str(excinfo.value)
    assert 'test_demo.py' in str(excinfo.value)
    assert source.read_text(encoding='utf-8') == 'def test_x(): pass'


@pytest.mark.parametrize(
    ('field', 'expected'),
    [
        ('json_path', '.json'),
        ('html_path', '.html or .htm'),
        ('md_path', '.md or .markdown'),
    ],
)
def test_every_sink_states_the_suffixes_it_accepts(field: str, expected: str) -> None:
    with pytest.raises(PytestGivenError) as excinfo:
        SinkConfig(**{field: Path('report.py')})
    assert f'must end in {expected}' in str(excinfo.value)


@pytest.mark.parametrize(
    'path', [Path('r.json'), Path('R.JSON'), Path('nested/dir/r.json')]
)
def test_a_well_formed_sink_path_is_accepted(path: Path) -> None:
    assert SinkConfig(json_path=path).json_path == path


def test_an_unexpected_render_failure_still_discards_the_stale_report(
    tmp_path, monkeypatch
):
    """`emit_sinks` promises the previous run's report never survives a failed
    one. A renderer bug raises something that is neither PytestGivenError nor
    OSError, and that promise has to hold for it too."""
    stale = tmp_path / 'report.json'
    stale.write_text('{"stale": true}')
    monkeypatch.setattr(
        sinks, 'render_sinks', lambda *_: (_ for _ in ()).throw(RuntimeError('boom'))
    )
    with pytest.raises(RuntimeError, match='boom'):
        sinks.emit_sinks({}, SinkConfig(json_path=stale))
    assert not stale.exists()


def _refs(*term_ids: str) -> tuple[ActivityPart, ...]:
    return tuple(ActivityTermRef(term_id=TermId(tid), display=tid) for tid in term_ids)


def _story_report() -> ReportData:
    """One story of an anchored activity (`guest search room`), an anchored one
    nothing narrates (`guest confirm booking`), and an under-anchored one
    (`guest browses listings`); a single bound scenario whose one step narrates
    the first."""
    story = Story(
        id=StoryId('book'),
        title='Book',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(ActivityPath(parts=_refs('guest', 'search', 'room')),),
            ),
            Activity(
                id=ActivityId(2),
                paths=(ActivityPath(parts=_refs('guest', 'confirm', 'booking')),),
            ),
            Activity(
                id=ActivityId(3),
                paths=(
                    ActivityPath(
                        parts=(
                            *_refs('guest'),
                            ActivityWord(text='browses'),
                            ActivityWord(text='listings'),
                        )
                    ),
                ),
            ),
        ),
    )
    step = Step(
        phase='when',
        narration=Narration(
            text='guest search room',
            parts=tuple(
                NarrationTermRef(term_id=TermId(tid), display=tid)
                for tid in ('guest', 'search', 'room')
            ),
        ),
    )
    return ReportData(
        metadata=Metadata(
            project='p', timestamp='t', pytest_version='8', plugin_version='0'
        ),
        scenarios=[
            Scenario(
                id=NodeId('tests/test_demo.py::test_demo'),
                narration=Narration(text='A demo scenario'),
                module='tests.test_demo',
                status='passed',
                steps=[step],
                story_id=StoryId('book'),
            )
        ],
        stories=[story],
    )


@scenario(
    t"The JSON report carries each {pg['Activity'].low}'s {pg['Coverage'].low}",
)
def test_json_sink_carries_per_activity_coverage(tmp_path: Path) -> None:
    with given(
        t'a {pg["Story"]} with a covered, an uncovered, an untracked {pg["Activity"]}'
    ):
        report = _story_report()
    with when('the JSON sink is rendered'):
        rendered = sinks.render_sinks(
            report_to_dict(report), SinkConfig(json_path=tmp_path / 'report.json')
        )
        data = json.loads(rendered.files[0].text)
    with then(t'a top-level `coverage` lists every {pg["Activity"].low} once'):
        assert data['coverage'] == [
            {
                'story_id': 'book',
                'activity_id': 1,
                'tracked': True,
                'scenario_ids': ['tests/test_demo.py::test_demo'],
            },
            {'story_id': 'book', 'activity_id': 2, 'tracked': True, 'scenario_ids': []},
            {
                'story_id': 'book',
                'activity_id': 3,
                'tracked': False,
                'scenario_ids': [],
            },
        ]
    with then('the rest of the report is the input dict, unchanged'):
        del data['coverage']
        assert data == report_to_dict(report)


@scenario(
    t'A re-rendered report recomputes {pg["Coverage"].low} rather than carrying it',
)
def test_json_sink_replaces_incoming_coverage(tmp_path: Path) -> None:
    with given('a saved report dict whose `coverage` no longer matches its steps'):
        stale = report_to_dict(_story_report())
        stale['coverage'] = ['stale']
    with when('`pytest-given report` re-renders it to JSON'):
        rendered = sinks.render_sinks(
            stale, SinkConfig(json_path=tmp_path / 'report.json')
        )
        data = json.loads(rendered.files[0].text)
    with then(
        t'the {pg["Coverage"].low} is the one the {pg["Step"].low}s actually earn'
    ):
        covered = [
            row['activity_id'] for row in data['coverage'] if row['scenario_ids']
        ]
        assert covered == [1]
