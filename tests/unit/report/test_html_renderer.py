import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    NodeId,
    ParameterColumn,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
    Story,
    StoryId,
    TermId,
    report_from_dict,
    report_to_dict,
)
from pytest_given.report.html_renderer import (
    _build_param_color_map,
    _inline_md,
    _make_activity_part_filter,
    _make_narration_filter,
    _neutralize_script_data,
    _render_narration_part,
    render_html,
)
from tests.ubiquitous_language import adopt_pytest_given, pg


def _narration(text: str, parts: list | None = None) -> dict:
    return {'text': text, 'parts': parts or []}


def test_inline_md_filter_blank_is_empty() -> None:
    assert _inline_md(None) == ''
    assert _inline_md('') == ''


def test_inline_md_filter_renders_markdown() -> None:
    assert _inline_md('**x** and `y`') == '<strong>x</strong> and <code>y</code>'


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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'debug log' in content
    assert 'some log output' in content
    assert 'assert 1 == 2' in content
    assert '- 1' in content


@scenario(
    t'{pg["Parameter coloring"]} marks placeholders and table headers',
    story=adopt_pytest_given,
)
def test_render_parametrized_step_with_structured_narration(tmp_path: Path) -> None:
    with given(
        t'a {pg["Report"]} holding a {pg["Parametrized scenario"]} '
        t'with a {pg["Parameter table"]}'
    ):
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
                                                'column_id': 'euros',
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
                                'columns': [
                                    {'id': 'euros', 'name': 'euros', 'kind': 'param'},
                                    {'id': 'expect', 'name': 'expect', 'kind': 'param'},
                                ],
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
    with when(t'the {pg["Renderer"]} renders the HTML page', activity=10):
        html_path = tmp_path / 'report.html'
        render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
        content = html_path.read_text(encoding='utf-8')
    with then(
        t'{pg["Parameter coloring"]} classes mark the grouped placeholder '
        t'and the table headers'
    ):
        assert 'param-color-0' in content
        # The grouped step shows the {name} token
        assert '{euros}' in content
        # Headers carry color class + data-param for the crosshair JS
        assert re.search(r'<th[^>]*\bparam-color-0\b[^>]*\bdata-param="euros"', content)
        assert re.search(
            r'<th[^>]*\bparam-color-1\b[^>]*\bdata-param="expect"', content
        )
    with then(
        t'the page carries one generated colour rule per column, after the '
        t'stylesheet so a term ref bound to a column takes the column ink'
    ):
        rules = re.findall(
            r'\.param-color-(\d+), th\.param-color-\1 \{ color: (#[0-9a-f]{6}); \}',
            content,
        )
        assert [index for index, _ in rules] == ['0', '1']
        assert len({color for _, color in rules}) == 2
        assert content.index('.param-color-0,') > content.index('.term-ref-actor {')


def test_render_grouped_placeholder_drops_format_spec_and_conversion(
    tmp_path: Path,
) -> None:
    """Grouped-template view shows a bare {name}: the schematic slot marks which
    column varies, not how a value prints. Conversion and format spec are
    per-value details applied in the concrete per-case rows, so they are
    dropped from the collapsed slot."""
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
                            'columns': [
                                {'id': 'n', 'name': 'n', 'kind': 'param'},
                                {'id': 'obj', 'name': 'obj', 'kind': 'param'},
                            ],
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
                                            'column_id': 'n',
                                            'format_spec': '03d',
                                            'conversion': None,
                                        },
                                        {'value': ' '},
                                        {
                                            'name': 'obj',
                                            'column_id': 'obj',
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert '{n}' in content
    assert '{obj}' in content
    assert '{n:03d}' not in content
    assert '{obj!r}' not in content


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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'config: {key: value}' in content


def test_render_value_part_uses_value_highlight_class(tmp_path: Path) -> None:
    """A NarrationValue (non-param t-string interpolation) gets .value-highlight."""
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'value-highlight' in content
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    # The template emits exactly two `</script>` tags (data block + alpine block).
    # An unescaped attachment payload would add a third.
    assert content.count('</script>') == 2
    # The escaped form must be present in the embedded JSON.
    assert '<\\/script>' in content


def test_render_escapes_script_close_in_node_id_blobs(tmp_path: Path) -> None:
    """A node id carrying `</script>` (via a parametrize id) flows into the
    derived `__scenarioSlugs`/`__termScenarios` blobs, not just the report data;
    every inline-script blob must neutralize `</` the same way."""
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
                        'id': 'tests/test_x.py::test_y[</script><img src=x>]',
                        'narration': _narration('XSS'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'parameters': None,
                        'error': None,
                        'steps': [],
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    # Two literal `</script>` tags only (data block + alpine block); an
    # unescaped node id in any blob would add a third.
    assert content.count('</script>') == 2


def test_render_escapes_comment_open_in_report_data(tmp_path: Path) -> None:
    """`</` is not the only sequence that steers the HTML tokenizer out of the
    inline `<script>`: `<!--` opens script-data-escaped state, and a `<script`
    after it reaches double-escaped state, where the template's own `</script>`
    stops terminating the element — swallowing the Alpine bundle and the rest of
    the document. A narration of `<!--<script>` is enough to trigger it."""
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
                        'narration': _narration('<!--<script>'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'parameters': None,
                        'error': None,
                        'steps': [],
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    # No raw `<!--` survives into the data blob; the escaped form carries the
    # same parsed value.
    script_start = content.index('window.__REPORT_DATA__')
    assert '<!--' not in content[script_start:]
    assert '\\u003C!--' in content
    # Both script blocks still close, so the document is not swallowed.
    assert content.count('</script>') == 2
    assert content.rstrip().endswith('</html>')


def test_neutralized_script_data_stays_valid_json() -> None:
    """The escapes must leave the blob parseable with the value unchanged —
    `\\/` and `\\u003C` are chosen over e.g. `\\!` for exactly that reason."""
    payload = {'a': '</script>', 'b': '<!--<script>'}
    neutralized = _neutralize_script_data(json.dumps(payload))
    assert '</' not in neutralized
    assert '<!--' not in neutralized
    assert json.loads(neutralized) == payload


def test_render_narration_part_rejects_unknown_variant() -> None:
    # The exhaustive match guards against a NarrationPart variant being added
    # without a render branch (silent drop). assert_never fires at runtime.
    with pytest.raises(AssertionError):
        _render_narration_part(cast(Any, object()), {}, None)


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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    # The tag rides in `data-tag` rather than in the click expression; see
    # test_report_data_never_lands_in_an_alpine_expression for why.
    assert 'data-tag="billing"' in content
    assert 'data-tag="happy-path"' in content
    assert 'filterByTag($el.dataset.tag)' in content
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'status-pill' in content
    assert 'showPassed' in content
    assert 'showFailed' in content
    assert 'showSkipped' in content


def _report_with_glossary(tmp_path: Path, *, terms: list[dict]) -> str:
    """Render a one-scenario report whose glossary carries `terms`."""
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
                        'narration': _narration('A scenario'),
                        'module': 'test_mod',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': None,
                        'error': None,
                    }
                ],
                'glossary': {'terms': terms},
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    return html_path.read_text(encoding='utf-8')


def test_render_includes_terms_browse_segment(tmp_path: Path) -> None:
    """A report with a glossary offers Terms as a third browse axis."""
    content = _report_with_glossary(
        tmp_path,
        terms=[
            {
                'id': 'guest',
                'kind': 'actor',
                'canonical': 'Guest',
                'definition': 'A person staying over.',
                'source': None,
            }
        ],
    )
    assert "view === 'terms'" in content
    assert '>Terms<' in content
    assert 'onGroupClick(group)' in content
    # The active-term chips read canonical names, not slug ids, and several
    # terms intersect rather than replacing one another.
    assert 'termLabel(termId)' in content
    assert 'x-for="termId in termFilters"' in content
    assert 'removeTermFilter(termId)' in content
    assert 'termNames[t.id] = t.canonical' in content


def test_render_omits_terms_segment_without_a_glossary(tmp_path: Path) -> None:
    """Without a glossary there is nothing to browse, so the segment is gone
    and app.js opens on Tags instead of an empty axis."""
    content = _report_with_glossary(tmp_path, terms=[])
    assert '>Terms<' not in content
    assert '>Tags<' in content
    assert '>Modules<' in content


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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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
                            'columns': [{'id': 'n', 'name': 'n', 'kind': 'param'}],
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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
        report_from_dict(json.loads(json_path.read_text())),
        html_path,
        source_link_template='vscode://file/{path}:{line}',
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'tests/test_x.py:9' in content
    assert '<a href="vscode' not in content


def test_render_includes_resolved_source_urls_when_template_set(tmp_path: Path) -> None:
    """When source_link_template is set and a Story/GlossaryTerm has a source,
    the resolved URL is computed by the renderer. We assert at the data-shape
    level by injecting a single scenario whose URL we can confirm — confirming
    the maps were populated. Story/term URL maps are exercised in later tasks
    once the template emits their link blocks."""
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
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': None,
                        'error': None,
                        'source': {'relpath': 'tests/test_x.py', 'line': 10},
                    },
                ],
                'stories': [],
                'glossary': None,
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(
        report_from_dict(json.loads(json_path.read_text())),
        html_path,
        source_link_template='vscode://file/{path}:{line}',
    )
    content = html_path.read_text(encoding='utf-8')
    assert 'vscode://file/' in content
    assert 'tests/test_x.py:10' in content


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
        report_from_dict(json.loads(json_path.read_text())),
        html_path,
        source_link_template='vscode://file/{path}:{line}',
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
                                            'column_id': 'euros',
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
                            'columns': [
                                {'id': 'euros', 'name': 'euros', 'kind': 'param'}
                            ],
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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
                            'columns': [
                                {'id': 'euros', 'name': 'euros', 'kind': 'param'},
                                {'id': 'expect', 'name': 'expect', 'kind': 'param'},
                            ],
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
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


def test_render_param_table_none_value_as_text_not_blank(tmp_path: Path) -> None:
    """A `None` parametrize value is a legitimate value on a `param` column
    (unlike a `derived`/`attachment` column, where `None` means "no value for
    this case"), so it must render, not blank out. Regression guard for a
    drift where this renderer briefly blanked `None` cells while the
    Markdown renderer kept printing the literal text."""
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
                        'id': 'test.py::test_none',
                        'narration': _narration('None param'),
                        'module': 'mod',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'steps': [],
                        'parameters': {
                            'columns': [
                                {'id': 'label', 'name': 'label', 'kind': 'param'},
                            ],
                            'cases': [
                                {'values': [None], 'status': 'passed', 'error': None},
                            ],
                        },
                        'error': None,
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert re.search(r'<td[^>]*\bdata-param="label"[^>]*>\s*None\s*</td>', content)


# ---------------------------------------------------------------------------
# NarrationTermRef rendering
# ---------------------------------------------------------------------------


def _glossary() -> Glossary:
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g._register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    g._register(GlossaryTerm(id=TermId('search'), kind='verb', canonical='search'))
    return g


def test_narration_filter_renders_actor_term_ref_with_actor_class() -> None:
    g = _glossary()
    f = _make_narration_filter(param_color_map={}, glossary=g)
    n = Narration(
        text='Guest',
        parts=[
            NarrationTermRef(term_id=TermId('guest'), display='Guest'),
        ],
    )
    assert 'term-ref-actor' in str(f(n))


def test_narration_filter_renders_object_term_ref_with_object_class() -> None:
    g = _glossary()
    f = _make_narration_filter(param_color_map={}, glossary=g)
    n = Narration(
        text='Room',
        parts=[
            NarrationTermRef(term_id=TermId('room'), display='Room'),
        ],
    )
    assert 'term-ref-object' in str(f(n))


def test_narration_filter_renders_verb_term_ref_with_verb_class() -> None:
    g = _glossary()
    f = _make_narration_filter(param_color_map={}, glossary=g)
    n = Narration(
        text='search',
        parts=[
            NarrationTermRef(term_id=TermId('search'), display='searches'),
        ],
    )
    assert 'term-ref-verb' in str(f(n))


def test_narration_filter_emits_tooltip_definition_when_term_has_one() -> None:
    g = Glossary()
    g._register(
        GlossaryTerm(
            id=TermId('guest'),
            kind='actor',
            canonical='Guest',
            definition='A person staying at the hotel.',
        )
    )
    f = _make_narration_filter(param_color_map={}, glossary=g)
    n = Narration(
        text='Guest',
        parts=[
            NarrationTermRef(term_id=TermId('guest'), display='Guest'),
        ],
    )
    out = str(f(n))
    assert 'data-term-name="Guest"' in out
    assert 'data-term-def="A person staying at the hotel."' in out


def test_narration_filter_includes_param_color_when_term_ref_has_param_column() -> None:
    g = _glossary()
    color_map = {'guest_name': 2}
    f = _make_narration_filter(param_color_map=color_map, glossary=g)
    n = Narration(
        text='Alice',
        parts=[
            NarrationTermRef(
                term_id=TermId('guest'),
                display='Alice',
                param_column='guest_name',
            ),
        ],
    )
    out = str(f(n))
    assert 'term-ref-actor' in out
    assert 'param-color-2' in out


def test_narration_filter_handles_term_ref_with_no_glossary_match() -> None:
    g = _glossary()
    f = _make_narration_filter(param_color_map={}, glossary=g)
    n = Narration(
        text='X',
        parts=[
            NarrationTermRef(term_id=TermId('missing'), display='X'),
        ],
    )
    out = str(f(n))
    assert 'X' in out
    assert 'term-ref' not in out


def test_narration_filter_with_no_glossary_falls_back_to_plain_text() -> None:
    """When the renderer is invoked with glossary=None (e.g. no glossary
    declared), NarrationTermRef still renders as escaped text."""
    f = _make_narration_filter(param_color_map={})  # glossary defaults to None
    n = Narration(
        text='X',
        parts=[
            NarrationTermRef(term_id=TermId('guest'), display='Guest'),
        ],
    )
    out = str(f(n))
    assert 'Guest' in out
    assert 'term-ref' not in out


# ---------------------------------------------------------------------------
# activity_part filter
# ---------------------------------------------------------------------------


def test_activity_part_filter_actor_term_ref():
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    f = _make_activity_part_filter(g)
    out = str(f(ActivityTermRef(term_id=TermId('guest'), display='Alice')))
    assert 'term-ref-actor' in out
    assert 'Alice' in out


def test_activity_part_filter_object_term_ref():
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    f = _make_activity_part_filter(g)
    out = str(f(ActivityTermRef(term_id=TermId('room'), display='Room')))
    assert 'term-ref-object' in out


def test_activity_part_filter_unknown_term_ref_falls_back():
    f = _make_activity_part_filter(Glossary())  # empty glossary
    out = str(f(ActivityTermRef(term_id=TermId('missing'), display='X')))
    assert 'term-ref-unknown' in out


def test_activity_part_filter_verb_term_ref_renders_verb_class():
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('search'), kind='verb', canonical='search'))
    f = _make_activity_part_filter(g)
    out = str(f(ActivityTermRef(term_id=TermId('search'), display='searches')))
    assert 'term-ref-verb' in out
    assert 'searches' in out


def test_activity_part_filter_word_renders_activity_word_class():
    f = _make_activity_part_filter(None)
    out = str(f(ActivityWord(text='for')))
    assert 'activity-word' in out
    assert 'for' in out


# ---------------------------------------------------------------------------
# stories coverage rollup computed in render_html
# ---------------------------------------------------------------------------


def test_render_with_story_computes_coverage_maps(tmp_path: Path) -> None:
    """render_html executes the stories-coverage rollup (lines 85, 90-107)
    when at least one scenario has a story_id and the report has a story."""
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
                'glossary': {
                    'terms': [
                        {
                            'id': 'guest',
                            'kind': 'actor',
                            'canonical': 'Guest',
                            'definition': '',
                        },
                        {
                            'id': 'search',
                            'kind': 'verb',
                            'canonical': 'search',
                            'definition': '',
                        },
                        {
                            'id': 'room',
                            'kind': 'object',
                            'canonical': 'Room',
                            'definition': '',
                        },
                    ]
                },
                'stories': [
                    {
                        'id': 'book-a-room',
                        'title': 'Book a Room',
                        'activities': [
                            {
                                'id': 1,
                                'paths': [
                                    {
                                        'parts': [
                                            {
                                                'term_id': 'guest',
                                                'display': 'Guest',
                                            },
                                            {
                                                'term_id': 'search',
                                                'display': 'searches',
                                            },
                                            {
                                                'term_id': 'room',
                                                'display': 'Room',
                                            },
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ],
                'scenarios': [
                    {
                        'id': 'test.py::test_book',
                        'narration': _narration('Book a room'),
                        'module': 'mod',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 5,
                        'steps': [
                            {
                                'phase': 'when',
                                'narration': _narration(
                                    'Guest searches Room',
                                    [
                                        {
                                            'type': 'term_ref',
                                            'term_id': 'guest',
                                            'display': 'Guest',
                                            'param_column': None,
                                        },
                                        {'value': ' '},
                                        {
                                            'type': 'term_ref',
                                            'term_id': 'search',
                                            'display': 'searches',
                                            'param_column': None,
                                        },
                                        {'value': ' '},
                                        {
                                            'type': 'term_ref',
                                            'term_id': 'room',
                                            'display': 'Room',
                                            'param_column': None,
                                        },
                                    ],
                                ),
                                'status': 'passed',
                                'children': [],
                                'attachments': [],
                                'error': None,
                            }
                        ],
                        'parameters': None,
                        'error': None,
                        'story_id': 'book-a-room',
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert html_path.exists()
    assert 'Book a Room' in content


def test_render_emits_term_scenario_index_global(tmp_path: Path) -> None:
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
                'glossary': {
                    'terms': [
                        {
                            'id': 'guest',
                            'kind': 'actor',
                            'canonical': 'Guest',
                            'definition': '',
                            'source': None,
                        },
                    ],
                },
                'scenarios': [
                    {
                        'id': 'test.py::test_x',
                        'narration': _narration('My Scenario'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 1,
                        'steps': [
                            {
                                'phase': 'when',
                                'narration': _narration(
                                    'a',
                                    [
                                        {'term_id': 'guest', 'display': 'Guest'},
                                    ],
                                ),
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert '__termScenarios' in content
    assert 'test.py::test_x' in content
    assert 'data-scenario-id="test.py::test_x"' in content


def test_render_round_trips_glossary_through_serde(tmp_path: Path) -> None:
    """The full pipeline — typed ReportData → report_to_dict → JSON → renderer
    — must preserve the Glossary so term refs render as kind pills, not as
    silent escape() fallbacks. Regression guard for the side-channel
    `_glossaries` stash that previously didn't round-trip."""
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g._register(GlossaryTerm(id=TermId('search'), kind='verb', canonical='search'))
    g._register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    story = Story(
        id=StoryId('book-a-room'),
        title='Book a Room',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            ActivityTermRef(term_id=TermId('guest'), display='Guest'),
                            ActivityTermRef(
                                term_id=TermId('search'), display='searches'
                            ),
                            ActivityTermRef(term_id=TermId('room'), display='Room'),
                        )
                    ),
                ),
            ),
        ),
    )
    scenario = Scenario(
        id=NodeId('test_book.py::test_x'),
        narration=Narration(text='Book a room'),
        module='m',
        steps=[
            Step(
                phase='when',
                narration=Narration(
                    text='Guest searches',
                    parts=[
                        NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                        NarrationLiteral(value=' '),
                        NarrationTermRef(term_id=TermId('search'), display='searches'),
                    ],
                ),
            )
        ],
        story_id=story.id,
    )
    report = ReportData(
        metadata=Metadata(
            project='p', timestamp='t', pytest_version='9', plugin_version='0.1'
        ),
        scenarios=[scenario],
        stories=[story],
        glossary=g,
    )

    json_path = tmp_path / 'data.json'
    json_path.write_text(json.dumps(report_to_dict(report)))
    rt = report_from_dict(json.loads(json_path.read_text()))
    assert rt.glossary is not None
    assert {t.id for t in rt.glossary.terms} == {'guest', 'search', 'room'}

    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'term-ref-actor' in content
    assert 'term-ref-verb' in content


def test_render_glossary_all_uncategorized_hides_kind_ui(tmp_path: Path) -> None:
    """When every term is uncategorized, the kind machinery is pure noise:
    no 'Show kinds' sidebar section and no 'Uncategorized' kind header. The
    terms themselves still render as a flat list."""
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
                'glossary': {
                    'terms': [
                        {'id': 'widget', 'kind': None, 'canonical': 'Widget'},
                        {'id': 'gadget', 'kind': None, 'canonical': 'Gadget'},
                    ],
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    # Kind filter section is gone.
    assert 'Show kinds' not in content
    # The 'Uncategorized' kind header is gone.
    assert 'kind-title term-kindless' not in content
    # But the terms still render.
    assert 'Widget' in content
    assert 'Gadget' in content


def test_render_glossary_with_categorized_terms_keeps_kind_ui(tmp_path: Path) -> None:
    """When at least one term is categorized, the kind machinery stays: the
    'Show kinds' sidebar section and the 'Uncategorized' header for the
    remaining kindless terms both render."""
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
                'glossary': {
                    'terms': [
                        {'id': 'guest', 'kind': 'actor', 'canonical': 'Guest'},
                        {'id': 'widget', 'kind': None, 'canonical': 'Widget'},
                    ],
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'Show kinds' in content
    assert 'kind-title term-kindless' in content
    # The header breakdown still names the kinds.
    assert '1 actor' in content
    assert '1 uncategorized' in content


def test_render_glossary_all_uncategorized_header_omits_kind_breakdown(
    tmp_path: Path,
) -> None:
    """With every term uncategorized, the header context collapses to just the
    term count — the '0 actors · 0 work objects · 0 verbs · N uncategorized'
    breakdown is noise and is dropped."""
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
                'glossary': {
                    'terms': [
                        {'id': 'widget', 'kind': None, 'canonical': 'Widget'},
                        {'id': 'gadget', 'kind': None, 'canonical': 'Gadget'},
                    ],
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert '2 terms' in content
    # These phrases only ever appear in the header breakdown.
    assert '0 actor' not in content
    assert 'work object' not in content
    assert 'uncategorized' not in content


def test_render_emits_short_scenario_slug_anchor_and_global(tmp_path: Path) -> None:
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
                        'id': 'pkg/test_booking.py::test_make',
                        'narration': _narration('Make a booking'),
                        'module': 'test_booking',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 1,
                        'steps': [],
                        'parameters': None,
                        'error': None,
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    # Anchor carries the short slug, not the raw node id.
    assert 'scenario=booking/make' in content
    assert 'scenario=pkg/test_booking.py::test_make' not in content
    # Reverse map global resolves slug -> node id.
    assert 'window.__scenarioSlugs = {' in content
    assert '"booking/make": "pkg/test_booking.py::test_make"' in content


# ---------------------------------------------------------------------------
# render_html accepts a ReportData model directly
# ---------------------------------------------------------------------------


def test_render_html_accepts_report_data(tmp_path: Path) -> None:
    report = report_from_dict(
        {
            'metadata': {
                'project': 'from-model',
                'timestamp': 't',
                'pytest_version': '9',
                'plugin_version': '0.1',
            },
            'scenarios': [],
        }
    )
    html_path = tmp_path / 'report.html'
    render_html(report, html_path)
    assert 'from-model' in html_path.read_text(encoding='utf-8')


# ---------------------------------------------------------------------------
# Alpine expression injection
#
# Alpine compiles a directive's *decoded* attribute text as JavaScript, so
# HTML-escaping a `'` to `&#39;` does not keep it out of the expression -- the
# parser hands the decoded `'` straight to `new Function`. Report data must
# therefore never be interpolated into an Alpine expression; it goes in a
# `data-*` attribute that the expression reads via `$el.dataset.*`.
#
# This asserts the property, not the markup: it names no element, class, or
# attribute, so it survives template restructuring and only fails if a value
# from the report reaches a directive as code.


_BREAKOUT = "'),__pwned(),('"


def _alpine_directive_values(html: str) -> list[tuple[str, str]]:
    """Every (name, decoded value) pair for attributes Alpine evaluates as JS."""
    found: list[tuple[str, str]] = []

    class _Collect(HTMLParser):
        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            for name, value in attrs:
                if value and name.startswith(('@', ':', 'x-')):
                    found.append((name, value))

    _Collect().feed(html)
    return found


def test_report_data_never_lands_in_an_alpine_expression(tmp_path: Path) -> None:
    """Every string the report model carries into a directive-bearing element,
    poisoned with a payload that closes a JS string literal and calls out."""
    report = report_from_dict(
        {
            'metadata': {
                'project': f'proj{_BREAKOUT}',
                'timestamp': 't',
                'pytest_version': '9',
                'plugin_version': '0.1',
            },
            'scenarios': [
                {
                    'id': f'test_a.py::test_b[{_BREAKOUT}]',
                    'narration': _narration('a scenario'),
                    'module': 'test_a',
                    'tags': [f'tag{_BREAKOUT}'],
                    'status': 'passed',
                    'steps': [],
                    'parameters': {
                        'columns': [
                            {
                                'id': f'param{_BREAKOUT}',
                                'name': f'param{_BREAKOUT}',
                                'kind': 'param',
                            },
                            {
                                'id': f'derived{_BREAKOUT}',
                                'name': f'derived{_BREAKOUT}',
                                'kind': 'derived',
                            },
                            {
                                'id': f'attachment{_BREAKOUT}',
                                'name': f'attachment{_BREAKOUT}',
                                'kind': 'attachment',
                            },
                        ],
                        'cases': [
                            {
                                'values': [
                                    'v',
                                    'd',
                                    {
                                        'label': f'att{_BREAKOUT}',
                                        'content': 'payload',
                                        'content_type': 'text',
                                    },
                                ],
                                'status': 'passed',
                            }
                        ],
                    },
                    'story_id': f'story{_BREAKOUT}',
                    'activity_ids': [f'act{_BREAKOUT}'],
                }
            ],
            'stories': [
                {
                    'id': f'story{_BREAKOUT}',
                    'title': 'a story',
                    'activities': [
                        {
                            'id': f'act{_BREAKOUT}',
                            'paths': [{'parts': [{'text': 'does a thing'}]}],
                        }
                    ],
                }
            ],
            'glossary': {
                'terms': [
                    {
                        'id': f'term{_BREAKOUT}',
                        'kind': 'actor',
                        'canonical': 'A Term',
                        'definition': 'a definition',
                    }
                ]
            },
        }
    )
    html_path = tmp_path / 'report.html'
    render_html(report, html_path)
    html = html_path.read_text(encoding='utf-8')

    # The payload must survive somewhere -- otherwise the poisoning silently
    # missed and the assertion below would pass for the wrong reason.
    assert '__pwned' in html
    offenders = [
        f'{name}="{value}"'
        for name, value in _alpine_directive_values(html)
        if '__pwned' in value
    ]
    assert not offenders, 'report data reached an Alpine expression: ' + '; '.join(
        offenders
    )


# ---------------------------------------------------------------------------
# typed parameter-table columns
# ---------------------------------------------------------------------------


def test_param_color_map_skips_attachment_columns() -> None:
    """An attachment column needs no value colour, so it is excluded from the
    colour map even while its sibling param column still gets one."""
    scenario = Scenario(
        id=NodeId('t.py::test_brew'),
        narration=Narration(text='brew'),
        module='t',
        parameters=ParameterTable(
            columns=[
                ParameterColumn(id='cup_size', name='cup_size', kind='param'),
                ParameterColumn(
                    id='attachment:0', name='machine state', kind='attachment'
                ),
            ],
            cases=[],
        ),
    )
    color_map = _build_param_color_map([scenario])
    assert color_map == {'cup_size': 0}


def test_a_disambiguated_columns_token_takes_its_own_columns_colour(
    tmp_path: Path,
) -> None:
    """The palette is keyed on the column *name*, so a token naming the column
    it points at reads the header's colour. A token still carrying the bare
    expression would take the first `price` column's colour while sitting under
    the second one's header."""
    report = report_from_dict(
        {
            'metadata': {
                'project': 'p',
                'timestamp': 't',
                'pytest_version': '9',
                'plugin_version': '0.1',
            },
            'scenarios': [
                {
                    'id': 't.py::test_brew',
                    'narration': _narration('brew'),
                    'module': 't',
                    'status': 'passed',
                    'steps': [
                        {
                            'phase': 'then',
                            'narration': {
                                'text': 'it costs {price #2}',
                                'parts': [
                                    {'value': 'it costs '},
                                    {'name': 'price #2', 'column_id': 'derived:1'},
                                ],
                            },
                        }
                    ],
                    'parameters': {
                        'columns': [
                            {'id': 'cup_size', 'name': 'cup_size', 'kind': 'param'},
                            {'id': 'derived:0', 'name': 'price', 'kind': 'derived'},
                            {'id': 'derived:1', 'name': 'price #2', 'kind': 'derived'},
                        ],
                        'cases': [{'values': [200, '2.0', '9.0'], 'status': 'passed'}],
                    },
                }
            ],
        }
    )
    html_path = tmp_path / 'report.html'
    render_html(report, html_path)
    html = html_path.read_text(encoding='utf-8')

    header = re.search(r'<th class="param-color-(\d+)" data-param="derived:1"', html)
    token = re.search(r'<span class="param-color-(\d+)" data-param="derived:1"', html)
    assert header is not None
    assert token is not None
    assert token.group(1) == header.group(1)


def test_render_prefers_the_title_over_the_project(tmp_path: Path) -> None:
    """`metadata.title`, when set, names the report in the browser tab and the
    topbar; `metadata.project` stays the rootdir name for source-link `{project}`."""
    report = report_from_dict(
        {
            'metadata': {
                'project': 'pytest-given',
                'title': 'Coffee Shop Example',
                'timestamp': 't',
                'pytest_version': '9',
                'plugin_version': '0.1',
            },
            'scenarios': [],
        }
    )
    html_path = tmp_path / 'report.html'
    render_html(report, html_path)
    content = html_path.read_text(encoding='utf-8')
    assert '<title>Coffee Shop Example — pytest-given Report</title>' in content
    assert '<div class="topbar-title">Coffee Shop Example</div>' in content


def test_render_embeds_activity_filter_data(tmp_path: Path) -> None:
    """The Scenarios view filters by activity in the browser, so the page has to
    carry both directions as data: which activities each scenario covers, and
    what each activity says. Neither is derivable from the story markup, which
    only paints the activity's prose as pills inside the Stories view."""
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
                'glossary': {
                    'terms': [
                        {'id': 'guest', 'kind': 'actor', 'canonical': 'Guest'},
                        {'id': 'search', 'kind': 'verb', 'canonical': 'search'},
                        {'id': 'room', 'kind': 'object', 'canonical': 'Room'},
                    ],
                },
                'stories': [
                    {
                        'id': 'book-a-room',
                        'title': 'Book a Room',
                        'activities': [
                            {
                                'id': 1,
                                'paths': [
                                    {
                                        'parts': [
                                            {'term_id': 'guest', 'display': 'Carol'},
                                            {
                                                'term_id': 'search',
                                                'display': 'searches for',
                                            },
                                            {'term_id': 'room', 'display': 'Room'},
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ],
                'scenarios': [
                    {
                        'id': 'test.py::test_x',
                        'narration': _narration('Carol searches'),
                        'module': 'm',
                        'tags': [],
                        'status': 'passed',
                        'duration_ms': 0,
                        'story_id': 'book-a-room',
                        'steps': [
                            {
                                'phase': 'when',
                                'narration': _narration(
                                    'Carol searches for a Room',
                                    [
                                        {'term_id': 'guest', 'display': 'Carol'},
                                        {
                                            'term_id': 'search',
                                            'display': 'searches for',
                                        },
                                        {'term_id': 'room', 'display': 'Room'},
                                    ],
                                ),
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
    render_html(report_from_dict(json.loads(json_path.read_text())), html_path)
    content = html_path.read_text(encoding='utf-8')
    assert 'window.__scenarioActivities = {"test.py::test_x": [1]};' in content
    assert (
        'window.__activityLabels = {"book-a-room:1": "Carol searches for Room"};'
        in content
    )
