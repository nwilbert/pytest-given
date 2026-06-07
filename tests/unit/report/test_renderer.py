import json
import re
from pathlib import Path

from pytest_given.report.renderer import render_html


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
                                    'frames': [],
                                    'error_tail': '- 1\n+ 2',
                                },
                            }
                        ],
                        'parameters': None,
                        'error': {
                            'message': 'assert 1 == 2',
                            'frames': [],
                            'error_tail': '- 1\n+ 2',
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
    # Headers carry color class + data-param so the crosshair JS can light them up
    assert re.search(r'<th[^>]*\bparam-color-0\b[^>]*\bdata-param="euros"', content)
    assert re.search(r'<th[^>]*\bparam-color-1\b[^>]*\bdata-param="expect"', content)


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


def test_render_escapes_script_close_in_report_data(tmp_path: Path) -> None:
    """Attachment content containing `</script>` must not break out of the
    inline `<script>` block — JSON doesn't escape `</` inside string literals,
    so the renderer must escape it on the way in."""
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
                        'narration': _narration('XSS'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'parameters': None,
                        'error': None,
                        'steps': [
                            {
                                'phase': 'then',
                                'narration': _narration('check'),
                                'status': 'passed',
                                'children': [],
                                'attachments': [
                                    {
                                        'label': 'payload',
                                        'content': '</script><script>alert(1)</script>',
                                    }
                                ],
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
    # The template emits exactly two `</script>` tags (data block + alpine block).
    # An unescaped attachment payload would add a third.
    assert content.count('</script>') == 2
    # The escaped form must be present in the embedded JSON.
    assert '<\\/script>' in content


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
                            'frames': [],
                            'error_tail': None,
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


def test_render_includes_skip_reason_block_and_chevron(tmp_path: Path) -> None:
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
                        'id': 't::x',
                        'narration': _narration('Skipped one'),
                        'module': 'mod',
                        'tags': [],
                        'status': 'skipped',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': None,
                        'error': None,
                        'skip_reason': 'awaiting fixture',
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'awaiting fixture' in content
    assert 'skip-reason' in content
    # Chevron present (scenario has a body): the placeholder span element is absent.
    assert '<span class="scenario-chevron-placeholder">' not in content


def test_render_skipped_without_reason_has_no_chevron(tmp_path: Path) -> None:
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
                        'id': 't::x',
                        'narration': _narration('Skipped no reason'),
                        'module': 'mod',
                        'tags': [],
                        'status': 'skipped',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': None,
                        'error': None,
                        'skip_reason': None,
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text(encoding='utf-8')
    assert '<span class="scenario-chevron-placeholder">' in content
    assert 'class="skip-reason"' not in content


def test_render_parameter_table_skipped_case_uses_dot_skipped(tmp_path: Path) -> None:
    """Skipped parametrize cases render ○ (dot-skipped), not ✗ (dot-failed)."""
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
                        'id': 't::x',
                        'narration': _narration('All skipped'),
                        'module': 'mod',
                        'tags': [],
                        'status': 'skipped',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': {
                            'names': ['n'],
                            'cases': [
                                {'values': [1], 'status': 'skipped', 'error': None},
                                {'values': [2], 'status': 'skipped', 'error': None},
                            ],
                        },
                        'error': None,
                        'skip_reason': None,
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text(encoding='utf-8')
    assert '<span class="dot-skipped">○</span>' in content
    assert '<span class="dot-failed">✗</span>' not in content


def test_renderer_emits_source_links_when_template_set(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'p',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                    'commit_sha': None,
                },
                'scenarios': [
                    {
                        'id': 'i',
                        'narration': _narration('S'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': None,
                        'error': None,
                        'source': {'relpath': 'tests/test_x.py', 'line': 9},
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(
        json_path, html_path, source_link_template='vscode://file/{path}:{line}'
    )
    content = html_path.read_text(encoding='utf-8')
    assert 'tests/test_x.py:9' in content
    assert 'vscode://file/' in content
    assert '<a href="vscode://file/' in content


def test_renderer_without_template_renders_plain_relpath(tmp_path: Path) -> None:
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
                        'narration': _narration('S'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': None,
                        'error': None,
                        'source': {'relpath': 'tests/test_x.py', 'line': 9},
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'tests/test_x.py:9' in content
    assert '<a href="vscode' not in content


def test_renderer_skips_link_block_when_scenario_has_no_source(
    tmp_path: Path,
) -> None:
    """Older JSON without `source` simply doesn't render the link row."""
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
                        'narration': _narration('S'),
                        'module': 'm',
                        'tags': [],
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
    render_html(
        json_path, html_path, source_link_template='vscode://file/{path}:{line}'
    )
    content = html_path.read_text(encoding='utf-8')
    # The CSS class is always emitted in the stylesheet; what we care about
    # is that no scenario-source <div> was rendered for this scenario.
    assert '<div class="scenario-source">' not in content


def test_render_placeholder_gets_data_param_attribute(tmp_path: Path) -> None:
    """Crosshair hover needs every placeholder span tagged with its param name."""
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
                                    'I insert 1',
                                    [
                                        {'value': 'I insert '},
                                        {
                                            'name': 'euros',
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
                        'parameters': {
                            'names': ['euros'],
                            'cases': [
                                {'values': [1], 'status': 'passed', 'error': None},
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
    assert 'data-param="euros"' in content
    # The placeholder span carries both class and data-param
    assert 'class="param-color-0" data-param="euros"' in content


def test_render_param_table_cells_get_data_param(tmp_path: Path) -> None:
    """Crosshair hover needs every <th>/<td> tagged with the column's param name."""
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
                        'steps': [],
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
    # Header carries data-param
    assert 'data-param="euros"' in content
    assert 'data-param="expect"' in content
    # td values are wrapped with data-param matching their column name; tolerate
    # additional attributes (Alpine handlers, etc.) between data-param and content
    assert re.search(r'<td[^>]*\bdata-param="euros"[^>]*>\s*1\s*</td>', content)
    assert re.search(r'<td[^>]*\bdata-param="expect"[^>]*>\s*False\s*</td>', content)
    assert re.search(r'<td[^>]*\bdata-param="euros"[^>]*>\s*2\s*</td>', content)
    assert re.search(r'<td[^>]*\bdata-param="expect"[^>]*>\s*True\s*</td>', content)
