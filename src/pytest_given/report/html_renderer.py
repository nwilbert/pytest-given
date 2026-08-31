import json
from collections.abc import Callable
from pathlib import Path

import jinja2
from markupsafe import Markup, escape

from ..model import (
    ActivityPart,
    ActivityTermRef,
    ActivityWord,
    AttachmentRef,
    Glossary,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    ReportData,
    Scenario,
    SourceLocation,
)
from .aggregations import (
    build_activity_labels,
    build_coverage_maps,
    build_glossary_aggregations,
    build_scenario_activity_index,
    build_story_rollups,
    build_term_scenario_index,
    tab_visibility,
)
from .inline_markdown import render_inline_markdown
from .palette import param_column_colors
from .slugs import build_scenario_slug_index
from .source_link import compile_source_link

_TEMPLATES_DIR = Path(__file__).parent / 'templates'

# Maps parameter name to its color index. The index resolves to a color via
# `palette.param_column_colors`, which never runs out.
type ParamColorMap = dict[str, int]


def _neutralize_script_data(text: str) -> str:
    """Escape the two sequences that let text embedded in an inline `<script>`
    steer the HTML tokenizer out of plain script-data state.

    - `</` closes the tag outright.
    - `<!--` opens script-data-*escaped* state; a `<script` after it reaches
      double-escaped state, where the template's own `</script>` no longer
      terminates the element and the rest of the document — the Alpine bundle
      included — is swallowed as script text.

    `\\/` and `\\u003C` are both valid JSON *and* JS escapes, so the blob stays
    parseable and the parsed value is unchanged, while the HTML parser sees
    neither sequence."""
    return text.replace('</', '<\\/').replace('<!--', '\\u003C!--')


def _script_json(value: object) -> Markup:
    """Serialize `value` to JSON for embedding in an inline `<script>`, with the
    tokenizer-steering sequences neutralized. `json.dumps` escapes neither of
    them inside string literals, and these blobs carry user-controlled node ids
    and activity prose.
    """
    return Markup(_neutralize_script_data(json.dumps(value)))


def _script_json_parse(value: object) -> Markup:
    """Serialize `value` as a `JSON.parse(...)` call rather than a JS object
    literal: an engine reads a JSON string faster than the equivalent source,
    and this is the largest blob on the page."""
    payload = json.dumps(json.dumps(value, separators=(',', ':')))
    return Markup('JSON.parse(' + _neutralize_script_data(payload) + ')')


def _app_data(report: ReportData) -> dict[str, object]:
    """The projection of the report that `app.js` seeds its state from.

    Not the whole report: everything the page displays is already rendered into
    the markup, and a second copy of every step, traceback and attachment
    payload was the biggest single thing in a large report's HTML. Adding a
    field to `reportApp` means adding it here."""
    return {
        'metadata': {'timestamp': report.metadata.timestamp},
        'glossary': (
            {
                'terms': [
                    {
                        'id': term.id,
                        'canonical': term.canonical,
                        'kind': term.kind,
                        'definition': term.definition,
                    }
                    for term in report.glossary.terms
                ]
            }
            if report.glossary is not None
            else None
        ),
        'scenarios': [
            {
                'id': scenario.id,
                'module': scenario.module,
                'tags': scenario.tags,
                'status': scenario.status,
                'story_id': scenario.story_id,
                'narration': {'text': scenario.narration.text},
            }
            for scenario in report.scenarios
        ],
    }


def _inline_md(text: str | None) -> Markup:
    """Jinja filter: render a term description's inline Markdown to safe HTML.

    The `not text` guard matters: `markupsafe.escape(None)` renders the literal
    string 'None', and `term.definition` is None for undefined terms."""
    if not text:
        return Markup('')
    return Markup(render_inline_markdown(text))


def render_html_string(
    report: ReportData,
    source_link_template: str | None = None,
) -> str:
    """Render a report model to a self-contained HTML document.

    `source_link_template` is the already-resolved template string (preset
    expansion happens before this point). None disables source linking.

    Returns the document rather than writing it — `sinks` owns the writing.
    """
    # Built once and handed to both: the narration filter colors placeholders
    # with it, and the template emits the matching `.param-color-N` rules.
    param_color_map = _build_param_color_map(report.scenarios)
    env = _build_env(report, source_link_template, param_color_map)
    html = env.get_template('report.html.j2').render(
        **_render_context(report, param_color_map)
    )
    assert isinstance(html, str)
    return html


def _build_env(
    report: ReportData,
    source_link_template: str | None,
    param_color_map: ParamColorMap,
) -> jinja2.Environment:
    """The Jinja environment: the template loader plus every filter and test
    the report templates call."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    env.globals['zip'] = zip
    # The step-tree macro branches on this: an AttachmentRef has no content to
    # expand, only a column to point at.
    env.tests['attachment_ref'] = lambda value: isinstance(value, AttachmentRef)
    env.filters['source_url'] = _make_source_url_filter(
        template=source_link_template,
        project=report.metadata.project,
        commit_sha=report.metadata.commit_sha,
    )
    env.filters['narration'] = _make_narration_filter(
        param_color_map,
        glossary=report.glossary,
    )
    env.filters['activity_part'] = _make_activity_part_filter(report.glossary)
    env.filters['inline_md'] = _inline_md
    return env


def _render_context(
    report: ReportData, param_color_map: ParamColorMap
) -> dict[str, object]:
    """Everything `report.html.j2` reads, in three groups: the report model
    itself, the precomputed aggregations, and the JSON blobs the page's Alpine
    state is seeded from."""
    coverage_maps = build_coverage_maps(report)
    scn_covers = build_scenario_activity_index(coverage_maps)
    activity_labels = build_activity_labels(report)
    term_scenario_index = build_term_scenario_index(report)
    scenario_slugs = build_scenario_slug_index(report)
    term_ids = [term.id for term in report.glossary.terms] if report.glossary else []
    return {
        'metadata': report.metadata,
        'scenarios': report.scenarios,
        'stories': report.stories,
        'glossary': report.glossary,
        'coverage_maps': coverage_maps,
        'glossary_aggregations': build_glossary_aggregations(report),
        'tab_visibility': tab_visibility(report),
        'story_rollups': build_story_rollups(report, coverage_maps),
        'scn_covers': scn_covers,
        'term_scenario_index': term_scenario_index,
        'scenario_slugs': scenario_slugs,
        'param_color_map': param_color_map,
        # The colors themselves, emitted as `.param-color-N` rules beside the
        # stylesheet. They are generated per report rather than sitting in
        # styles.css, because how many a report needs is a property of the
        # report.
        'param_colors': param_column_colors(len(param_color_map)),
        'scenario_activities_json': _script_json(scn_covers),
        'activity_labels_json': _script_json(activity_labels),
        'story_ids_json': _script_json([story.id for story in report.stories]),
        'term_ids_json': _script_json(term_ids),
        'term_scenarios_json': _script_json(term_scenario_index),
        'scenario_slugs_json': _script_json(
            {slug: node_id for node_id, slug in scenario_slugs.items()}
        ),
        'app_data_js': _script_json_parse(_app_data(report)),
        **_bundled_assets(),
    }


def _bundled_assets() -> dict[str, Markup]:
    """The stylesheet and scripts inlined into the page — the whole reason the
    report needs no server and no external asset."""
    return {
        name: Markup((_TEMPLATES_DIR / filename).read_text(encoding='utf-8'))
        for name, filename in (
            ('css', 'styles.css'),
            ('app_js', 'app.js'),
            ('alpine_js', 'alpine.min.js'),
        )
    }


def _build_param_color_map(scenarios: list[Scenario]) -> ParamColorMap:
    """One color per column *name* across the report, so a parameter reads the
    same color in every scenario. Attachment columns are excluded — a badge
    needs no value color."""
    color_map: ParamColorMap = {}
    color_idx = 0
    for scenario in scenarios:
        if scenario.parameters is None:
            continue
        for column in scenario.parameters.columns:
            if column.kind == 'attachment':
                continue
            if column.name not in color_map:
                color_map[column.name] = color_idx
                color_idx += 1
    return color_map


def _make_source_url_filter(
    *,
    template: str | None,
    project: str,
    commit_sha: str | None,
) -> Callable[[SourceLocation | None], str | None]:
    """Build a Jinja filter that resolves a SourceLocation to a URL string.

    Returns None when source linking is disabled or the source is absent — the
    template reads that as "render a plain `<span>`". The template itself is
    validated and parsed once here, not per location.
    """
    substitute = (
        None
        if template is None
        else compile_source_link(template, project=project, commit_sha=commit_sha)
    )

    def _filter(source: SourceLocation | None) -> str | None:
        if source is None or substitute is None:
            return None
        return substitute(source)

    return _filter


def _make_narration_filter(
    param_color_map: ParamColorMap,
    glossary: Glossary | None = None,
) -> Callable[[Narration], Markup]:
    """Jinja filter: renders a `Narration` to HTML, part by part.

    Usage: `{{ step.narration | narration }}`. A parts-less narration (a plain
    string label) is escaped and emitted verbatim.
    """

    def _render(narration: Narration) -> Markup:
        if not narration.parts:
            return Markup(str(escape(narration.text)))
        out = [
            _render_narration_part(part, param_color_map, glossary)
            for part in narration.parts
        ]
        return Markup(''.join(out))

    return _render


def _render_narration_part(
    part: NarrationPart,
    param_color_map: ParamColorMap,
    glossary: Glossary | None,
) -> str:
    """Render one `NarrationPart` to an HTML fragment."""
    match part:
        case NarrationLiteral(value=value):
            return str(escape(value))
        case NarrationValue(rendered=rendered):
            return f'<span class="value-highlight">{escape(rendered)}</span>'
        case NarrationPlaceholder(name=name, column_id=column_id):
            color_idx = param_color_map.get(name, 0)
            label = _placeholder_token(part)
            # `data-param` keys the hover highlight and carries the column *id*
            # — two steps can interpolate the same expression with different
            # values, which would cross-wire if the name were the key. The
            # palette keys on `name` instead, so one parameter reads the same
            # color everywhere. `data-subst` is row-hover substitution's own.
            #
            # Both are plain data-*, read back by the delegated hover listener
            # in `app.js`. No Alpine directive here: interpolating into one
            # would be an injection, since Alpine compiles a directive's
            # *decoded* attribute text as JS.
            safe_id = escape(column_id)
            return (
                f'<span class="param-color-{color_idx}" '
                f'data-param="{safe_id}" '
                f'data-subst="{safe_id}"'
                f'>{escape(label)}</span>'
            )
        case NarrationTermRef():
            return _render_term_ref(part, glossary)


_TERM_KIND_CLASSES: dict[str | None, str] = {
    'actor': 'term-ref-actor',
    'object': 'term-ref-object',
    'verb': 'term-ref-verb',
}


def _term_kind_class(kind: str | None) -> str:
    """The CSS class for a term's kind. A kind still deferred to inference —
    or one this renderer does not know — falls back, and `dict.get` already
    reads `None` as a miss."""
    return _TERM_KIND_CLASSES.get(kind, 'term-ref-unknown')


def _term_ref_span(
    *,
    classes: list[str],
    display: str,
    term_id: str | None = None,
    tooltip_name: str = '',
    tooltip_def: str = '',
) -> str:
    ref_classes = list(classes)
    if term_id is not None:
        ref_classes.append('term-ref--link')
    if tooltip_name:
        ref_classes.append('has-term-tip')
    attrs = [f'class="{" ".join(ref_classes)}"']
    if term_id is not None:
        attrs.append(f'data-term-id="{escape(term_id)}"')
    # The custom hover tooltip (see app.js) reads the canonical name and
    # definition off these attributes; it replaces the native `title` so the
    # term name can show as a styled heading above its definition.
    if tooltip_name:
        attrs.append(f'data-term-name="{escape(tooltip_name)}"')
        if tooltip_def:
            rendered_def = render_inline_markdown(tooltip_def)
            attrs.append(f'data-term-def="{escape(rendered_def)}"')
    return f'<span {" ".join(attrs)}>{escape(display)}</span>'


def _render_term_ref(part: NarrationTermRef, glossary: Glossary | None) -> str:
    term = glossary.get(part.term_id) if glossary is not None else None
    if term is None:
        return str(escape(part.display))
    return _term_ref_span(
        classes=[_term_kind_class(term.kind)],
        display=part.display,
        term_id=part.term_id,
        tooltip_name=term.canonical,
        tooltip_def=term.definition or '',
    )


def _placeholder_token(part: NarrationPlaceholder) -> str:
    """Render the grouped-template slot as a bare `{name}`.

    The grouped view is schematic — it marks *which* column varies, not how any
    one value prints. Conversion and format spec are already applied in the
    concrete per-case rows, so they are noise in the collapsed slot and are
    dropped here (still stored on the placeholder for the paths that need
    them)."""
    return '{' + part.name + '}'


def _make_activity_part_filter(
    glossary: Glossary | None,
) -> Callable[[ActivityPart], Markup]:
    """Jinja filter: renders a single `ActivityPart` to HTML.

    Usage: `{{ part | activity_part }}`
    """

    def _render(part: ActivityPart) -> Markup:
        match part:
            case ActivityTermRef(term_id=tid, display=display):
                term = glossary.get(tid) if glossary else None
                return Markup(
                    _term_ref_span(
                        classes=[_term_kind_class(term.kind if term else None)],
                        display=display,
                        term_id=tid,
                        tooltip_name=term.canonical if term else '',
                        tooltip_def=term.definition or '' if term else '',
                    )
                )
            case ActivityWord(text=text):
                return Markup(f'<span class="activity-word">{escape(text)}</span>')

    return _render
