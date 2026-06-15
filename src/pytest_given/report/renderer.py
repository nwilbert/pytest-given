import json
from collections.abc import Callable
from pathlib import Path

import jinja2
from markupsafe import Markup, escape

from ..model import (
    ActivityEntity,
    ActivityId,
    ActivityPart,
    ActivityPlaceholder,
    ActivityTerm,
    ActivityWord,
    Glossary,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    Scenario,
    SourceLocation,
    StoryId,
    TermId,
    report_from_dict,
)
from .aggregations import (
    build_coverage_maps,
    build_glossary_aggregations,
    tab_visibility,
)
from .source_link import format_source_link

_NUM_PARAM_COLORS = 6

# Maps parameter name to its color index (0-based, wraps at _NUM_PARAM_COLORS)
type ParamColorMap = dict[str, int]


def render_html(
    json_path: Path,
    html_path: Path,
    source_link_template: str | None = None,
) -> None:
    """Render a JSON report to a self-contained HTML file.

    `source_link_template` is the already-resolved template string (preset
    expansion happens before this point). None disables source linking;
    each scenario then renders a plain `<span>` for its source location.
    """
    raw_json = json_path.read_text(encoding='utf-8')
    report = report_from_dict(json.loads(raw_json))
    # JSON doesn't escape `</` inside string literals, but we embed `raw_json`
    # inside an inline <script>; an attachment containing `</script>` would
    # close the tag and yield stored XSS. `\/` is a valid JSON/JS escape for
    # `/`, so this preserves the parsed value while neutering the HTML parser.
    safe_report_json = raw_json.replace('</', '<\\/')

    templates_dir = Path(__file__).parent / 'templates'
    css = (templates_dir / 'styles.css').read_text(encoding='utf-8')
    app_js = (templates_dir / 'app.js').read_text(encoding='utf-8')
    alpine_js = (templates_dir / 'alpine.min.js').read_text(encoding='utf-8')

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )
    env.globals['zip'] = zip

    param_color_map = _build_param_color_map(report.scenarios)

    project = report.metadata.project
    commit_sha = report.metadata.commit_sha

    source_urls: dict[int, str | None] = {
        idx: _resolve_url(
            scn.source,
            template=source_link_template,
            project=project,
            commit_sha=commit_sha,
        )
        for idx, scn in enumerate(report.scenarios)
    }
    story_source_urls: dict[StoryId, str | None] = {
        story.id: _resolve_url(
            story.source,
            template=source_link_template,
            project=project,
            commit_sha=commit_sha,
        )
        for story in report.stories
    }
    term_source_urls: dict[TermId, str | None] = {
        term.id: _resolve_url(
            term.source,
            template=source_link_template,
            project=project,
            commit_sha=commit_sha,
        )
        for term in (report.glossary.terms if report.glossary is not None else ())
    }

    coverage_maps = build_coverage_maps(report)
    glossary_aggregations = build_glossary_aggregations(report)
    visibility = tab_visibility(report)

    scenarios_by_story_id: dict[StoryId, list[Scenario]] = {}
    for scn in report.scenarios:
        if scn.story_id is None:
            continue
        scenarios_by_story_id.setdefault(scn.story_id, []).append(scn)

    stories_coverage_rollup: dict[StoryId, dict[ActivityId, dict]] = {}
    stories_coverage_by_scenario: dict[str, list[NodeId]] = {}
    for story in report.stories:
        per_activity: dict[ActivityId, dict] = {}
        for activity in story.activities:
            covered_by: list[NodeId] = []
            passed = 0
            total = 0
            for scn in scenarios_by_story_id.get(story.id, []):
                if activity.id in coverage_maps[scn.id]:
                    covered_by.append(scn.id)
                    total += 1
                    if scn.status == 'passed':
                        passed += 1
            per_activity[activity.id] = {
                'scenario_ids': covered_by,
                'passed': passed,
                'total': total,
            }
            stories_coverage_by_scenario[f'{story.id}:{activity.id}'] = covered_by
        stories_coverage_rollup[story.id] = per_activity

    scn_covers: dict[NodeId, list[ActivityId]] = {
        scn.id: sorted(coverage_maps[scn.id].keys()) for scn in report.scenarios
    }

    total_scenarios_per_story = {
        sid: len(scns) for sid, scns in scenarios_by_story_id.items()
    }

    story_ids_json = Markup(json.dumps([story.id for story in report.stories]))
    term_ids_json = Markup(
        json.dumps(
            [term.id for term in report.glossary.terms]
            if report.glossary is not None
            else []
        )
    )

    env.filters['narration'] = _make_narration_filter(
        param_color_map,
        glossary=report.glossary,
    )
    env.filters['activity_part'] = _make_activity_part_filter(report.glossary)
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=report.metadata,
        scenarios=report.scenarios,
        stories=report.stories,
        glossary=report.glossary,
        coverage_maps=coverage_maps,
        glossary_aggregations=glossary_aggregations,
        tab_visibility=visibility,
        stories_coverage=stories_coverage_rollup,
        stories_coverage_by_scenario=stories_coverage_by_scenario,
        scenarios_for_story=scenarios_by_story_id,
        scn_covers=scn_covers,
        total_scenarios_per_story=total_scenarios_per_story,
        report_json=Markup(safe_report_json),
        story_ids_json=story_ids_json,
        term_ids_json=term_ids_json,
        css=Markup(css),
        app_js=Markup(app_js),
        alpine_js=Markup(alpine_js),
        param_color_map=param_color_map,
        num_param_colors=_NUM_PARAM_COLORS,
        source_urls=source_urls,
        story_source_urls=story_source_urls,
        term_source_urls=term_source_urls,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding='utf-8')


def _build_param_color_map(scenarios: list[Scenario]) -> ParamColorMap:
    color_map: ParamColorMap = {}
    color_idx = 0
    for scenario in scenarios:
        if scenario.parameters is None:
            continue
        for name in scenario.parameters.names:
            if name not in color_map:
                color_map[name] = color_idx
                color_idx += 1
    return color_map


def _resolve_url(
    source: SourceLocation | None,
    *,
    template: str | None,
    project: str,
    commit_sha: str | None,
) -> str | None:
    if source is None or template is None:
        return None
    return format_source_link(
        template, source=source, project=project, commit_sha=commit_sha
    )


def _make_narration_filter(
    param_color_map: ParamColorMap,
    glossary: Glossary | None = None,
) -> Callable[[Narration], Markup]:
    """Filter usage: `{{ step.narration | narration }}` or
    `{{ scenario.narration | narration }}`.

    The narration is a `Narration` dataclass with a flat `text` and a list
    of typed `NarrationPart` variants:
      - `NarrationLiteral` → escape `value`
      - `NarrationValue`   → `.param-value` highlight around `rendered`
      - `NarrationPlaceholder` → color-coded `{name!conv:spec}` token
      - `NarrationTermRef` → kind-coloured pill resolved via glossary
    Empty parts → escape `text` and emit verbatim.
    """

    def _render(narration: Narration) -> Markup:
        if not narration.parts:
            return Markup(str(escape(narration.text)))
        out: list[str] = []
        for part in narration.parts:
            match part:
                case NarrationLiteral(value=value):
                    out.append(str(escape(value)))
                case NarrationValue(rendered=rendered):
                    out.append(f'<span class="param-value">{escape(rendered)}</span>')
                case NarrationPlaceholder(name=name):
                    color_idx = param_color_map.get(name, 0) % _NUM_PARAM_COLORS
                    label = _placeholder_token(part)
                    # Single-quote the JS arg because the HTML attribute is "..."
                    # and parametrize names are Python identifiers (no `'`).
                    safe_name = escape(name)
                    enter = f"setHoverParam('{safe_name}', $event.currentTarget)"
                    leave = 'setHoverParam(null, $event.currentTarget)'
                    out.append(
                        f'<span class="param-color-{color_idx}" '
                        f'data-param="{safe_name}" '
                        f'@mouseenter="{enter}" '
                        f'@mouseleave="{leave}"'
                        f'>{escape(label)}</span>'
                    )
                case NarrationTermRef():
                    out.append(_render_term_ref(part, glossary, param_color_map))
        return Markup(''.join(out))

    return _render


_TERM_KIND_CLASSES = {
    'actor': 'term-ref-actor',
    'object': 'term-ref-object',
    'verb': 'term-ref-verb',
}


def _term_pill(
    *,
    classes: list[str],
    display: str,
    term_id: str | None = None,
    title: str = '',
) -> str:
    attrs = [f'class="{" ".join(classes)}"']
    if term_id is not None:
        attrs.append(f'data-term-id="{escape(term_id)}"')
    if title:
        attrs.append(f'title="{escape(title)}"')
    return f'<span {" ".join(attrs)}>{escape(display)}</span>'


def _render_term_ref(
    part: NarrationTermRef,
    glossary: Glossary | None,
    param_color_map: ParamColorMap,
) -> str:
    term = glossary.get(part.term_id) if glossary is not None else None
    if term is None:
        return str(escape(part.display))
    classes = [_TERM_KIND_CLASSES[term.kind]]
    if part.param_column is not None:
        color_idx = param_color_map.get(part.param_column, 0) % _NUM_PARAM_COLORS
        classes.append(f'param-color-{color_idx}')
    return _term_pill(
        classes=classes,
        display=part.display,
        term_id=part.term_id,
        title=term.definition or '',
    )


def _placeholder_token(part: NarrationPlaceholder) -> str:
    """Reconstruct the source-side `{name!conv:spec}` token, so the merged
    template view preserves the author's format intent."""
    inner = part.name
    if part.conversion:
        inner += '!' + part.conversion
    if part.format_spec:
        inner += ':' + part.format_spec
    return '{' + inner + '}'


def _make_activity_part_filter(
    glossary: Glossary | None,
) -> Callable[[ActivityPart], Markup]:
    """Jinja filter: renders a single `ActivityPart` to HTML.

    Usage: `{{ part | activity_part }}`
    """

    def _render(part: ActivityPart) -> Markup:
        match part:
            case ActivityEntity(entity_id=tid, display=display):
                term = glossary.get(tid) if glossary else None
                kind_class = (
                    _TERM_KIND_CLASSES[term.kind]
                    if term is not None
                    else 'term-ref-unknown'
                )
                return Markup(
                    _term_pill(
                        classes=[kind_class],
                        display=display,
                        term_id=tid,
                        title=term.definition if term else '',
                    )
                )
            case ActivityTerm(term_id=tid, display=display):
                return Markup(
                    _term_pill(
                        classes=[_TERM_KIND_CLASSES['verb']],
                        display=display,
                        term_id=tid,
                    )
                )
            case ActivityWord(text=text):
                return Markup(f'<span class="activity-word">{escape(text)}</span>')
            case ActivityPlaceholder(kind=kind, text=text):
                return Markup(
                    _term_pill(
                        classes=[_TERM_KIND_CLASSES[kind], 'is-draft'],
                        display=text,
                        title='Draft — promote to glossary to lock in',
                    )
                )

    return _render
