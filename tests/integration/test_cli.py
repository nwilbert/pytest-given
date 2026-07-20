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


def test_cli_no_command() -> None:
    rc = main([])
    assert rc == 1


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


def test_cli_diagrams_generates_artifact(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        from pytest_given import Glossary, activity, given, scenario, story

        g = Glossary()
        barista = g.actor('Barista')
        brew = g.verb('brew')
        coffee = g.work_object('Coffee')

        serve_coffee = story('Serve Coffee', [activity(barista, brew('brews'), coffee)])

        @scenario('Barista brews', story=serve_coffee)
        def test_brew():
            with given('a bean'):
                pass
        """
    )
    json_path = pytester.path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    diagrams_path = pytester.path / 'out' / 'diagrams.html'
    rc = main(['report', str(json_path), '--diagrams', str(diagrams_path)])
    assert rc == 0
    assert diagrams_path.exists()
    assert 'Serve Coffee' in diagrams_path.read_text(encoding='utf-8')


def test_cli_format_md_to_stdout_with_diagrams_keeps_stdout_clean(
    tmp_path: Path, capsys
) -> None:
    """--format md with no -o writes the markdown payload to stdout; the
    'Diagrams generated: ...' status line must not join it there, or piping
    the CLI's stdout to a file corrupts the markdown."""
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
                'stories': [{'id': 'empty', 'title': 'Empty', 'activities': []}],
            }
        )
    )
    diagrams_path = tmp_path / 'diagrams.html'
    rc = main(
        ['report', str(json_path), '--format', 'md', '--diagrams', str(diagrams_path)]
    )
    assert rc == 0
    assert diagrams_path.exists()
    captured = capsys.readouterr()
    assert captured.out == '# pytest-given — cli\n\n'
    assert 'Diagrams generated' in captured.err
    assert 'Diagrams generated' not in captured.out
