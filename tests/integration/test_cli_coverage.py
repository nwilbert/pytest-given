import json
from dataclasses import replace
from pathlib import Path

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.cli import main
from pytest_given.model import ReportData, report_to_dict
from tests.ubiquitous_language import pg
from tests.unit.report.story_report import story_report


@scenario(
    t"`pytest-given coverage` prints each {pg['Sentence'].l}'s {pg['Coverage'].l}",
    tags=['spec/report-schema-validation'],
)
def test_coverage_prints_each_sentences_scenarios(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with given(
        t'a {pg["Report"].l} whose {pg["Story"].l} has a covered, an uncovered '
        t'and an untracked {pg["Sentence"].l}'
    ):
        report_file = _written(tmp_path, story_report())
    with when('`pytest-given coverage` reads it'):
        exit_code = main(['coverage', str(report_file)])
        printed = capsys.readouterr()
    with then(t'stdout lists every {pg["Sentence"].l} once, with its scenarios'):
        assert json.loads(printed.out) == [
            {
                'story_id': 'book',
                'sentence_id': 1,
                'tracked': True,
                'scenario_ids': ['tests/test_demo.py::test_demo'],
            },
            {'story_id': 'book', 'sentence_id': 2, 'tracked': True, 'scenario_ids': []},
            {
                'story_id': 'book',
                'sentence_id': 3,
                'tracked': False,
                'scenario_ids': [],
            },
        ]
    with then(
        t'it exits 1, naming how many tracked {pg["Sentence"].l}s have no scenario'
    ):
        assert exit_code == 1
        assert printed.err == '1 tracked sentence has no scenario.\n'


def test_coverage_exits_0_when_every_tracked_sentence_has_a_scenario(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = story_report()
    story = report.stories[0]
    covered_only = replace(
        report, stories=[replace(story, sentences=story.sentences[:1])]
    )
    assert main(['coverage', str(_written(tmp_path, covered_only))]) == 0
    printed = capsys.readouterr()
    assert [record['sentence_id'] for record in json.loads(printed.out)] == [1]
    assert printed.err == ''


def test_coverage_reads_the_default_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'given-report').mkdir()
    _written(tmp_path / 'given-report', story_report(), 'report-data.json')
    assert main(['coverage']) == 1
    assert len(json.loads(capsys.readouterr().out)) == 3


@pytest.mark.parametrize(
    ('content', 'message'),
    [
        (None, 'not found'),
        ('{"metadata": {"schema_version": 1}, "scenarios": 3}', 'is not a valid'),
        ('{"metadata": {"schema_version": 2}, "scenarios": []}', 'schema version 2'),
    ],
)
def test_coverage_exits_2_on_a_report_it_cannot_read(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    content: str | None,
    message: str,
) -> None:
    report_file = tmp_path / 'report.json'
    if content is not None:
        report_file.write_text(content, encoding='utf-8')
    assert main(['coverage', str(report_file)]) == 2
    printed = capsys.readouterr()
    assert printed.out == ''
    assert printed.err.startswith('Error: ')
    assert message in printed.err


def _written(directory: Path, report: ReportData, name: str = 'report.json') -> Path:
    report_file = directory / name
    report_file.write_text(json.dumps(report_to_dict(report)), encoding='utf-8')
    return report_file
