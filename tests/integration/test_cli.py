import json
from pathlib import Path

import pytest

from pytest_given.cli import main


def test_cli_generates_html(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'cli-test',
                    'timestamp': '2026-04-09',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'out.html'
    rc = main(['report', str(json_path), '-o', str(html_path)])
    assert rc == 0
    assert html_path.exists()
    assert 'cli-test' in html_path.read_text(encoding='utf-8')


def test_cli_missing_input_file(tmp_path: Path) -> None:
    rc = main(['report', str(tmp_path / 'nonexistent.json')])
    assert rc == 1


def test_cli_no_command(capsys) -> None:
    """argparse owns the usage error, so a bare invocation exits 2 like any
    other CLI rather than printing help and calling it a failure."""
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
    assert 'report' in capsys.readouterr().err


def _scenario_with_source(relpath: str = 'tests/x.py', line: int = 2) -> dict:
    return {
        'id': 'i',
        'narration': {'text': 'S', 'parts': []},
        'module': 'm',
        'tags': [],
        'status': 'passed',
        'duration_ms': 0,
        'steps': [],
        'parameters': None,
        'error': None,
        'source': {'relpath': relpath, 'line': line},
    }


def test_cli_source_link_preset(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'p',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [_scenario_with_source()],
            }
        )
    )
    html_path = tmp_path / 'out.html'
    rc = main(
        [
            'report',
            str(json_path),
            '-o',
            str(html_path),
            '--source-link',
            'zed',
        ]
    )
    assert rc == 0
    content = html_path.read_text(encoding='utf-8')
    assert '<a href="zed://file/' in content


def test_cli_source_link_none_renders_plain_span(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'p',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [_scenario_with_source()],
            }
        )
    )
    html_path = tmp_path / 'out.html'
    rc = main(['report', str(json_path), '-o', str(html_path)])
    assert rc == 0
    content = html_path.read_text(encoding='utf-8')
    assert 'tests/x.py:2' in content
    assert '<a href="zed' not in content


def test_cli_format_md_to_stdout(tmp_path, capsys) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'cli',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [
                    {
                        'id': 'tests/t.py::test_a',
                        'narration': {'text': 'Alpha', 'parts': []},
                        'module': 'tests/t.py',
                        'tags': [],
                        'status': 'passed',
                        'steps': [
                            {'phase': 'when', 'narration': {'text': 'act', 'parts': []}}
                        ],
                    }
                ],
            }
        )
    )
    rc = main(['report', str(json_path), '--format', 'md'])
    assert rc == 0
    assert '## ✓ Alpha' in capsys.readouterr().out


def test_cli_md_inferred_from_output_extension(tmp_path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'cli',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [],
            }
        )
    )
    out = tmp_path / 'r.md'
    rc = main(['report', str(json_path), '-o', str(out)])
    assert rc == 0
    assert out.read_text(encoding='utf-8').startswith('# pytest-given — cli')


def test_cli_md_creates_missing_parent_dirs(tmp_path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'cli',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [],
            }
        )
    )
    out = tmp_path / 'nested' / 'dir' / 'r.md'
    rc = main(['report', str(json_path), '--format', 'md', '-o', str(out)])
    assert rc == 0
    assert out.read_text(encoding='utf-8').startswith('# pytest-given — cli')


def _minimal_report() -> dict:
    return {
        'metadata': {
            'project': 'cli-test',
            'timestamp': '2026-04-09',
            'pytest_version': '9',
            'plugin_version': '0.1',
        },
        'scenarios': [],
    }


def test_cli_reports_malformed_json_without_a_traceback(tmp_path: Path, capsys) -> None:
    """A truncated or hand-edited report is a file problem, not a crash."""
    json_path = tmp_path / 'data.json'
    json_path.write_text('{"metadata": ', encoding='utf-8')
    rc = main(['report', str(json_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert 'Error' in err
    assert 'Traceback' not in err


def test_cli_reports_a_stale_report_without_a_traceback(tmp_path: Path, capsys) -> None:
    """`serde` raises PytestGivenError for a report written by an older
    pytest-given precisely so this path can say so — the message exists to
    avoid a bare KeyError surfacing out of `pytest-given report`."""
    data = _minimal_report()
    data['scenarios'] = [
        {
            'id': 'i',
            'narration': {'text': 'S', 'parts': []},
            'module': 'm',
            'tags': [],
            'status': 'passed',
            'duration_ms': 0,
            'steps': [],
            # A pre-`columns` parameter table: the shape serde rejects.
            'parameters': {'names': ['a'], 'cases': []},
        }
    ]
    json_path = tmp_path / 'data.json'
    json_path.write_text(json.dumps(data), encoding='utf-8')
    rc = main(['report', str(json_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert 'Error' in err
    assert 'Traceback' not in err


@pytest.mark.parametrize(
    'payload',
    [
        pytest.param({'scenarios': []}, id='missing-key'),
        pytest.param([1, 2], id='not-an-object'),
        pytest.param({**_minimal_report(), 'glossary': 7}, id='member-of-wrong-type'),
        pytest.param(
            {**_minimal_report(), 'scenarios': ['nope']}, id='scenario-not-an-object'
        ),
    ],
)
def test_cli_reports_a_report_of_the_wrong_shape_without_a_traceback(
    payload: object, tmp_path: Path, capsys
) -> None:
    """JSON that parses but is not a pytest-given report.

    `report_from_dict` indexes what it is handed, so each of these surfaces as a
    different builtin from deep inside serde — `KeyError`, `TypeError`,
    `AttributeError`. The CLI owes the user one message either way.
    """
    json_path = tmp_path / 'data.json'
    json_path.write_text(json.dumps(payload), encoding='utf-8')
    rc = main(['report', str(json_path), '-o', str(tmp_path / 'o.html')])
    assert rc == 1
    err = capsys.readouterr().err
    assert 'not a pytest-given report' in err
    assert 'Traceback' not in err


def test_cli_reports_an_unknown_source_link_preset_without_a_traceback(
    tmp_path: Path, capsys
) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(json.dumps(_minimal_report()), encoding='utf-8')
    rc = main(
        [
            'report',
            str(json_path),
            '-o',
            str(tmp_path / 'o.html'),
            '--source-link',
            'no-such-editor',
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert 'Error' in err
    assert 'Traceback' not in err


def test_cli_write_failure_discards_the_stale_report(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """`pytest-given report` gets the plugin's all-or-nothing guarantee: a
    failed write must not leave the previous run's report reading as current.
    """
    json_path = tmp_path / 'data.json'
    json_path.write_text(json.dumps(_minimal_report()), encoding='utf-8')
    html_path = tmp_path / 'out.html'
    html_path.write_text('previous run', encoding='utf-8')

    def refuse(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError('read-only file system')

    monkeypatch.setattr(Path, 'write_text', refuse)
    rc = main(['report', str(json_path), '-o', str(html_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert 'read-only file system' in err
    assert 'would read as current' in err
