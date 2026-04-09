import json
from pathlib import Path

from pytest_given.renderer import render_html


def test_render_produces_html_file(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'test-proj',
                    'timestamp': '2026-04-09T00:00:00Z',
                    'pytest_version': '9.0',
                    'plugin_version': '0.1.0',
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    assert html_path.exists()
    content = html_path.read_text()
    assert 'test-proj' in content
    assert 'x-data' in content


def test_render_includes_scenario_data(tmp_path: Path) -> None:
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
                'scenarios': [
                    {
                        'id': 'test.py::test_x',
                        'name': 'My Scenario',
                        'module': 'test_mod',
                        'tags': ['billing'],
                        'status': 'passed',
                        'duration_ms': 10,
                        'steps': [
                            {
                                'phase': 'given',
                                'text': 'a thing',
                                'status': 'passed',
                                'source': None,
                                'children': [],
                                'attachments': [],
                                'error': None,
                            }
                        ],
                        'parameters': None,
                        'error': None,
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text()
    assert 'My Scenario' in content
    assert 'billing' in content
    assert 'a thing' in content


def test_render_self_contained(tmp_path: Path) -> None:
    """The output HTML has no external dependencies (except Alpine.js CDN for now)."""
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
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text()
    assert '<style>' in content
    assert '<script>' in content
