import json
from pathlib import Path

from pytest_given.renderer import render_html


def _narration(text: str, parts: list | None = None) -> dict:
    return {'text': text, 'parts': parts or []}


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
    content = html_path.read_text(encoding='utf-8')
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
                        'narration': _narration('My Scenario'),
                        'module': 'test_mod',
                        'tags': ['billing'],
                        'status': 'passed',
                        'duration_ms': 10,
                        'steps': [
                            {
                                'phase': 'given',
                                'narration': _narration('a thing'),
                                'status': 'passed',
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
    content = html_path.read_text(encoding='utf-8')
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
                        'narration': _narration('Err Scenario'),
                        'module': 'test_mod',
                        'tags': [],
                        'status': 'failed',
                        'duration_ms': 5,
                        'steps': [
                            {
                                'phase': 'then',
                                'narration': _narration('check value'),
                                'status': 'failed',
                                'children': [
                                    {
                                        'phase': 'then',
                                        'narration': _narration('nested check'),
                                        'status': 'passed',
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
    content = html_path.read_text(encoding='utf-8')
    assert 'debug log' in content
    assert 'some log output' in content
    assert 'assert 1 == 2' in content
    assert '- 1' in content


def test_render_parameterized_step_with_structured_narration(tmp_path: Path) -> None:
    """Merged parametric step renders placeholder with color span and {name} token."""
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
                        'narration': _narration('Param scenario'),
                        'module': 'mod',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [
                            {
                                'phase': 'when',
                                'narration': _narration(
                                    'I insert 1 into shop',
                                    [
                                        {'value': 'I insert '},
                                        {
                                            'name': 'euros',
                                            'format_spec': '',
                                            'conversion': None,
                                        },
                                        {'value': ' into shop'},
                                    ],
                                ),
                                'status': 'passed',
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
    content = html_path.read_text(encoding='utf-8')
    assert 'param-color-0' in content
    # The merged step shows the {name} token
    assert '{euros}' in content
    # The header still gets its color
    assert '<th class="param-color-0">euros</th>' in content
    assert '<th class="param-color-1">expect</th>' in content


def test_render_merged_placeholder_preserves_format_spec_and_conversion(
    tmp_path: Path,
) -> None:
    """Merged-template view shows {name!conv:spec} so the author's format
    intent stays visible to the reader."""
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
                        'id': 'i',
                        'narration': _narration('n'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'error': None,
                        'parameters': {
                            'names': ['n', 'obj'],
                            'cases': [
                                {
                                    'values': [7, 'hi'],
                                    'status': 'passed',
                                    'error': None,
                                },
                            ],
                        },
                        'steps': [
                            {
                                'phase': 'when',
                                'narration': _narration(
                                    'x',
                                    [
                                        {
                                            'name': 'n',
                                            'format_spec': '03d',
                                            'conversion': None,
                                        },
                                        {'value': ' '},
                                        {
                                            'name': 'obj',
                                            'format_spec': '',
                                            'conversion': 'r',
                                        },
                                    ],
                                ),
                                'status': 'passed',
                                'children': [],
                                'attachments': [],
                                'error': None,
                            }
                        ],
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text(encoding='utf-8')
    assert '{n:03d}' in content
    assert '{obj!r}' in content


def test_render_plain_str_step_with_empty_parts_escapes_braces(
    tmp_path: Path,
) -> None:
    """A plain-string step renders verbatim, with no regex pass over braces."""
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
                        'id': 'i',
                        'narration': _narration('n'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'parameters': None,
                        'error': None,
                        'steps': [
                            {
                                'phase': 'when',
                                'narration': _narration('config: {key: value}'),
                                'status': 'passed',
                                'children': [],
                                'attachments': [],
                                'error': None,
                            }
                        ],
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'config: {key: value}' in content


def test_render_value_part_uses_param_value_class(tmp_path: Path) -> None:
    """A NarrationValue (non-param t-string interpolation) gets .param-value."""
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
                        'id': 'i',
                        'narration': _narration('n'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'parameters': None,
                        'error': None,
                        'steps': [
                            {
                                'phase': 'when',
                                'narration': _narration(
                                    'cost: 12.0',
                                    [
                                        {'value': 'cost: '},
                                        {
                                            'rendered': '12.0',
                                            'expression': 'price * 1.2',
                                            'format_spec': '',
                                            'conversion': None,
                                        },
                                    ],
                                ),
                                'status': 'passed',
                                'children': [],
                                'attachments': [],
                                'error': None,
                            }
                        ],
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'param-value' in content
    assert '12.0' in content


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
    content = html_path.read_text(encoding='utf-8')
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
                        'narration': _narration('Tagged Scenario'),
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
    content = html_path.read_text(encoding='utf-8')
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
                        'narration': _narration('Passing'),
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
                        'narration': _narration('Failing'),
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
    content = html_path.read_text(encoding='utf-8')
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
    content = html_path.read_text(encoding='utf-8')
    assert 'status-pill' in content
    assert 'showPassed' in content
    assert 'showFailed' in content
    assert 'showSkipped' in content
