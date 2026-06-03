import json
from pathlib import Path

from pytest_given.report.cli import main


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
