"""Reports to cite, built from the model for the citation tests."""

from pytest_given.model import (
    Metadata,
    Narration,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    Status,
    Story,
    StoryId,
    param_id,
)

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


def report_(
    *scenarios: Scenario,
    stories: tuple[Story, ...] = (),
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
    )
