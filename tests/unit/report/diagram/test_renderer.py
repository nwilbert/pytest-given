from pathlib import Path

from pytest_given.model import Glossary, Metadata, ReportData, Story
from pytest_given.report import render_diagrams


def _report(trip_story: Story, trip_glossary: Glossary) -> ReportData:
    return ReportData(
        metadata=Metadata(
            project='demo', timestamp='2026-07-19T00:00:00+00:00',
            pytest_version='9', plugin_version='0.1.0', commit_sha=None,
        ),
        scenarios=[],
        stories=[trip_story],
        glossary=trip_glossary,
    )


def test_writes_self_contained_file_with_story_data(
    tmp_path: Path, trip_story: Story, trip_glossary: Glossary
) -> None:
    output = tmp_path / 'sub' / 'diagrams.html'
    render_diagrams(_report(trip_story, trip_glossary), output)
    html = output.read_text(encoding='utf-8')
    assert trip_story.id in html          # deep-link anchor data
    assert trip_story.title in html
    assert 'Individual traveler.' in html  # tooltip definition payload
    assert 'src=' not in html              # self-contained: no external refs


def test_no_glossary_and_empty_story(tmp_path: Path, trip_story: Story) -> None:
    from pytest_given.model import StoryId

    empty = Story(id=StoryId('empty'), title='Empty Story', activities=())
    report = _report(trip_story, None)
    report.stories.append(empty)
    output = tmp_path / 'diagrams.html'
    render_diagrams(report, output)
    html = output.read_text(encoding='utf-8')
    assert 'Empty Story' in html           # renders with empty-state note


def test_label_lines_wraps_near_midpoint() -> None:
    from pytest_given.report.diagram.renderer import _label_lines

    assert _label_lines('Booking') == ['Booking']
    assert _label_lines('unbreakable-very-long-identifier') == [
        'unbreakable-very-long-identifier'
    ]
    assert _label_lines('group trip payment confirmation') == [
        'group trip payment', 'confirmation'
    ]
