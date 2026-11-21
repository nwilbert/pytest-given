"""Unit tests for the sink render/write/discard split (`report/sinks.py`)."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from pytest_given import PytestGivenError, given, scenario, then, when
from pytest_given.model import (
    Definition,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
    NodeId,
    ReportData,
    ReportUrl,
    Scenario,
    SourceLocation,
    TermId,
    report_to_dict,
)
from pytest_given.report import sinks
from pytest_given.report.sinks import SinkConfig, discard_files
from tests.ubiquitous_language import pg
from tests.unit.report.app_data import embedded_app_data
from tests.unit.report.story_report import story_report


def test_discarding_removes_the_paths_this_run_would_have_written(
    tmp_path,
) -> None:
    stale = tmp_path / 'report.html'
    stale.write_text('previous run', encoding='utf-8')
    notes = discard_files(SinkConfig(html_path=stale).file_paths())
    assert not stale.exists()
    assert notes == [f'Removed the previous {stale} — it would read as current.']


def test_discarding_reports_an_unlink_failure_instead_of_raising(
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
    [note] = discard_files(SinkConfig(html_path=stale).file_paths())
    assert note == f'Could not remove the previous {stale}: read-only file system'


def test_a_sink_path_that_cannot_be_a_report_file_is_refused(tmp_path) -> None:
    """A bare `--given-html` consumes the next argument, so a mis-ordered
    invocation would otherwise aim the renderer at the user's own source file —
    and the discard would then unlink it as a stale report."""
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
        sinks.emit_sinks(dict, SinkConfig(json_path=stale))
    assert not stale.exists()


def _report_dict() -> dict[str, object]:
    """The smallest report every sink renders: no scenarios, no stories."""
    return report_to_dict(
        ReportData(
            metadata=Metadata(
                project='p', timestamp='t', pytest_version='9', plugin_version='0.1'
            ),
            scenarios=[],
        )
    )


def test_an_interrupted_write_leaves_no_sink_and_no_temporary(tmp_path, monkeypatch):
    """Nothing moves into place until every file is written."""
    json_path, md_path = tmp_path / 'report.json', tmp_path / 'report.md'
    _interrupt_temporary(monkeypatch, number=2)
    with pytest.raises(KeyboardInterrupt):
        sinks.emit_sinks(_report_dict, SinkConfig(json_path=json_path, md_path=md_path))
    assert list(tmp_path.iterdir()) == []


def test_an_interrupted_write_discards_the_stale_report(tmp_path, monkeypatch):
    stale = tmp_path / 'report.json'
    stale.write_text('{"stale": true}')
    _interrupt_temporary(monkeypatch, number=1)
    with pytest.raises(KeyboardInterrupt):
        sinks.emit_sinks(_report_dict, SinkConfig(json_path=stale))
    assert not stale.exists()


def _interrupt_temporary(monkeypatch: pytest.MonkeyPatch, *, number: int) -> None:
    """A Ctrl-C while the `number`th staged temporary is written."""
    real_write = Path.write_text
    seen: list[Path] = []

    def write_text(self, data, *args, **kwargs):
        if self.name.endswith('.tmp'):
            seen.append(self)
            if len(seen) == number:
                raise KeyboardInterrupt
        return real_write(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', write_text)


def test_the_json_sink_writes_the_dict_it_is_handed(tmp_path: Path) -> None:
    report_dict = report_to_dict(story_report())
    rendered = sinks.render_sinks(
        report_dict, SinkConfig(json_path=tmp_path / 'report.json')
    )
    assert json.loads(rendered.files[0].text) == report_dict


@scenario(
    t'A written {pg["Report"].l} names its JSON schema',
    tags=['spec/report-schema-validation'],
)
def test_a_written_report_names_its_schema(tmp_path: Path) -> None:
    with given(t'a {pg["Report"].l} with one story'):
        report_dict = report_to_dict(story_report())
    with when(t'the JSON sink writes the {pg["Report"].l}'):
        rendered = sinks.render_sinks(
            report_dict, SinkConfig(json_path=tmp_path / 'report.json')
        )
        written = json.loads(rendered.files[0].text)
    with then('`$schema` is its first key'):
        assert next(iter(written)) == '$schema'
    with then('it names the schema the documentation site publishes'):
        assert written['$schema'] == (
            'https://nwilbert.github.io/pytest-given/latest/schemas/'
            'report-v1.schema.json'
        )


def test_md_source_reads_the_test_files_under_the_source_root(tmp_path: Path) -> None:
    """Under the source root, not the working directory, which pytester runs
    happen to share with their rootdir."""
    (tmp_path / 'test_a.py').write_text(
        'def test_a():\n    assert True\n', encoding='utf-8', newline='\n'
    )
    report = ReportData(
        metadata=Metadata(
            project='p', timestamp='t', pytest_version='9', plugin_version='0'
        ),
        scenarios=[
            Scenario(
                id=NodeId('test_a.py::test_a'),
                narration=Narration(text='A'),
                module='test_a',
                status='passed',
                source=SourceLocation(relpath='test_a.py', line=1),
            )
        ],
    )
    config = SinkConfig(md_to_stdout=True, md_source=True, source_root=tmp_path)

    rendered = sinks.render_sinks(report_to_dict(report), config)

    assert rendered.md_stdout is not None
    assert '1  def test_a():\n2      assert True\n```' in rendered.md_stdout


def _glossary_report(*, definitions: bool = True) -> ReportData:
    """`story_report` with a glossary of its three anchors and a report URL."""
    glossary = Glossary()
    for term_id, kind in (
        ('guest', 'actor'),
        ('search', 'activity'),
        ('room', 'object'),
    ):
        glossary.register(
            GlossaryTerm(
                id=TermId(term_id),
                kind=kind,
                canonical=term_id,
                definition=(
                    Definition(
                        text=f'The {term_id}.',
                        parts=(NarrationLiteral(value=f'The {term_id}.'),),
                    )
                    if definitions
                    else None
                ),
            )
        )
    report = story_report()
    return replace(
        report,
        glossary=glossary,
        metadata=replace(
            report.metadata, report_url=ReportUrl('https://example.org/report.html')
        ),
    )


def test_glossary_only_html_drops_scenarios_stories_and_report_url(
    tmp_path: Path,
) -> None:
    report = _glossary_report()
    rendered = sinks.render_sinks(
        report_to_dict(report),
        SinkConfig(
            json_path=tmp_path / 'report.json',
            html_path=tmp_path / 'report.html',
            html_glossary_only=True,
        ),
    )
    json_file, html_file = rendered.files
    app_data = embedded_app_data(html_file.text)
    assert app_data['views'] == ['glossary']
    assert app_data['scenarios'] == []
    assert app_data['story_ids'] == []
    assert app_data['citations'] is None
    assert 'A demo scenario' not in html_file.text
    assert [scn['id'] for scn in json.loads(json_file.text)['scenarios']] == [
        'tests/test_demo.py::test_demo'
    ]


@pytest.mark.parametrize('glossary', [None, Glossary()], ids=['none', 'no-terms'])
def test_glossary_only_refuses_a_report_without_glossary_terms(
    tmp_path: Path, glossary: Glossary | None
) -> None:
    report = replace(story_report(), glossary=glossary)
    with pytest.raises(PytestGivenError, match='glossary'):
        sinks.render_sinks(
            report_to_dict(report),
            SinkConfig(html_path=tmp_path / 'report.html', html_glossary_only=True),
        )


def test_glossary_only_renders_a_glossary_without_definitions(tmp_path: Path) -> None:
    report = _glossary_report(definitions=False)
    [html_file] = sinks.render_sinks(
        report_to_dict(report),
        SinkConfig(html_path=tmp_path / 'report.html', html_glossary_only=True),
    ).files
    assert embedded_app_data(html_file.text)['views'] == ['glossary']


@pytest.mark.parametrize(
    ('config', 'message'),
    [
        (
            {
                'html_path': Path('r.html'),
                'report_url': ReportUrl('https://e.org/r.html'),
            },
            'report URL',
        ),
        ({'json_path': Path('r.json')}, 'HTML'),
    ],
    ids=['with-report-url', 'without-html'],
)
def test_a_glossary_only_config_that_cannot_render_is_refused(
    config: dict, message: str
) -> None:
    with pytest.raises(PytestGivenError, match=message):
        SinkConfig(html_glossary_only=True, **config)
