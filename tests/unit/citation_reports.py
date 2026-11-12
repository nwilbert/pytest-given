"""Reports to cite, built from the model for the citation tests."""

from pytest_given.model import (
    Definition,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationTermRef,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    Status,
    Step,
    Story,
    StoryId,
    TermId,
    narration_of,
    param_id,
)
from pytest_given.report.citation_index import CitationTemplate

URL = 'https://example.org/report.html'


def scenario_(
    node_id: str,
    title: str = 'A title',
    *,
    status: Status = 'passed',
    tags: tuple[str, ...] = (),
    grouped: bool = False,
    other_cases: tuple[str, ...] = (),
    stories: tuple[str, ...] = (),
) -> Scenario:
    table = (
        ParameterTable(
            columns=[ParameterColumn(id=param_id('x'), name='x', kind='param')],
            cases=[
                ParameterCase(id=NodeId(case_id), values=[1], status=status)
                for case_id in (node_id, *other_cases)
            ],
        )
        if grouped
        else None
    )
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text=title),
        module='m',
        status=status,
        tags=list(tags),
        parameters=table,
        story_ids=tuple(StoryId(story) for story in stories),
    )


def story_(story_id: str, title: str | None = None) -> Story:
    return Story(
        id=StoryId(story_id),
        title=story_id if title is None else title,
        sentences=(Sentence(id=SentenceId(1), clauses=()),),
    )


def term_(name: str, definition: str | None = None) -> GlossaryTerm:
    return GlossaryTerm(
        id=TermId(name.lower()),
        kind='actor',
        canonical=name,
        definition=None if definition is None else Definition.literal(definition),
    )


def using_(term_id: str, used_by: Scenario) -> Scenario:
    """`used_by` with a further step holding a term ref to `term_id`."""
    used_by.steps = [
        *used_by.steps,
        Step(
            phase='given',
            narration=narration_of(
                [NarrationTermRef(term_id=TermId(term_id), display=term_id)]
            ),
        ),
    ]
    return used_by


def filled(template: CitationTemplate, row: list[str]) -> str:
    """As `app.js` fills a template: literal text and slot names alternate."""
    glyph, fragment, title, summary, html_title = [*row, '', ''][:5]
    values = {
        'glyph': glyph,
        'fragment': fragment,
        'title': title,
        'html_title': html_title or title,
        'summary': summary,
    }
    return ''.join(
        part if position % 2 == 0 else values[part]
        for position, part in enumerate(template)
    )


def report_(
    *scenarios: Scenario,
    stories: tuple[Story, ...] = (),
    terms: tuple[GlossaryTerm, ...] = (),
    report_url: str | None = URL,
) -> ReportData:
    return ReportData(
        metadata=Metadata(
            project='p',
            timestamp='t',
            pytest_version='9',
            plugin_version='0',
            report_url=report_url,
        ),
        scenarios=list(scenarios),
        stories=list(stories),
        glossary=Glossary(terms=list(terms)) if terms else None,
    )
