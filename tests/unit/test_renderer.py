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


def test_render_attachments_and_errors(tmp_path: Path) -> None:
    """Renderer handles steps with attachments and errors."""
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
                        'name': 'Err Scenario',
                        'module': 'test_mod',
                        'tags': [],
                        'status': 'failed',
                        'duration_ms': 5,
                        'steps': [
                            {
                                'phase': 'then',
                                'text': 'check value',
                                'status': 'failed',
                                'source': None,
                                'children': [
                                    {
                                        'phase': 'then',
                                        'text': 'nested check',
                                        'status': 'passed',
                                        'source': None,
                                        'children': [],
                                        'attachments': [],
                                        'error': None,
                                    }
                                ],
                                'attachments': [
                                    {
                                        'label': 'debug log',
                                        'content': 'some log output',
                                    }
                                ],
                                'error': {
                                    'message': 'assert 1 == 2',
                                    'diff': '- 1\n+ 2',
                                },
                            }
                        ],
                        'parameters': None,
                        'error': {
                            'message': 'assert 1 == 2',
                            'diff': '- 1\n+ 2',
                        },
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text()
    assert 'debug log' in content
    assert 'some log output' in content
    assert 'assert 1 == 2' in content
    assert '- 1' in content


def test_render_parameterized_with_color_coded_placeholders(tmp_path: Path) -> None:
    """Parameterized scenarios get color-coded placeholders in step text and headers."""
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
                        'id': 'test.py::test_p',
                        'name': 'Param scenario',
                        'module': 'mod',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [
                            {
                                'phase': 'when',
                                'text': 'I insert {euros} into {unknown}',
                                'status': 'passed',
                                'source': None,
                                'children': [],
                                'attachments': [],
                                'error': None,
                            }
                        ],
                        'parameters': {
                            'names': ['euros', 'expect'],
                            'cases': [
                                {
                                    'values': [1, False],
                                    'status': 'passed',
                                    'error': None,
                                },
                                {
                                    'values': [2, True],
                                    'status': 'passed',
                                    'error': None,
                                },
                            ],
                        },
                        'error': None,
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text()
    # Placeholder in step text should be wrapped in a color span
    assert 'param-color-0' in content
    # Column header should use the same color class
    assert '<th class="param-color-0">euros</th>' in content
    assert '<th class="param-color-1">expect</th>' in content
    # Unknown placeholders are left as plain text (not wrapped in a color span)
    assert '{unknown}' in content


def test_render_self_contained(tmp_path: Path) -> None:
    """The output HTML has no external dependencies."""
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
    assert 'src="http' not in content
    assert 'href="http' not in content


def test_render_clickable_tag_badges(tmp_path: Path) -> None:
    """Tag badges on scenario cards include click handler for filtering."""
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
                        'name': 'Tagged Scenario',
                        'module': 'test_mod',
                        'tags': ['billing', 'happy-path'],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [],
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
    assert "filterByTag('billing')" in content
    assert "filterByTag('happy-path')" in content
    assert 'scenario-tag' in content


def test_render_scenarios_collapsed_by_default_failed_expanded(tmp_path: Path) -> None:
    """Scenarios are collapsed by default; failed ones auto-expand."""
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
                        'id': 'test.py::test_pass',
                        'name': 'Passing',
                        'module': 'mod',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': None,
                        'error': None,
                    },
                    {
                        'id': 'test.py::test_fail',
                        'name': 'Failing',
                        'module': 'mod',
                        'tags': [],
                        'status': 'failed',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': None,
                        'error': {
                            'message': 'boom',
                            'diff': None,
                        },
                    },
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text()
    assert 'expandedScenarios' in content
    assert 'toggleScenario' in content


def test_render_status_filter_pills(tmp_path: Path) -> None:
    """Report includes clickable status filter pills in sidebar."""
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
    assert 'status-pill' in content
    assert 'status-bar' in content
    assert 'showPassed' in content
    assert 'showFailed' in content
    assert 'showSkipped' in content
