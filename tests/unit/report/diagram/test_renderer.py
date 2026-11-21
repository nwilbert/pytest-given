from pytest_given.model import Glossary, Metadata, ReportData, Story, StoryId
from pytest_given.report.diagram import layout_stories, render_diagrams_html
from pytest_given.report.diagram.renderer import label_lines


def _report(trip_story: Story, trip_glossary: Glossary) -> ReportData:
    return ReportData(
        metadata=Metadata(
            project='demo',
            timestamp='2026-07-19T00:00:00+00:00',
            pytest_version='9',
            plugin_version='0.1.0',
            commit_sha=None,
        ),
        scenarios=[],
        stories=[trip_story],
        glossary=trip_glossary,
    )


def test_renders_a_self_contained_page_with_story_data(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    html = render_diagrams_html(
        report := _report(trip_story, trip_glossary), layout_stories(report)
    )
    assert trip_story.id in html  # deep-link anchor data
    assert trip_story.title in html
    assert 'Individual traveler.' in html  # tooltip definition payload
    assert f'{len(trip_story.sentences)} sentences' in html  # sidebar count
    assert '<script src=' not in html  # self-contained: no external refs


def test_no_glossary_and_empty_story(trip_story: Story) -> None:
    empty = Story(id=StoryId('empty'), title='Empty Story', sentences=())
    report = _report(trip_story, None)
    report.stories.append(empty)
    html = render_diagrams_html(report, layout_stories(report))
    assert 'Empty Story' in html  # renders with empty-state note
    assert 'This story has no sentences yet.' in html


def test_no_stories_at_all_renders_empty_state() -> None:
    """A run with zero stories (e.g. coffeeshop, which has none) must render a
    sane empty-state page, not crash and not a blank body."""
    report = ReportData(
        metadata=Metadata(
            project='demo',
            timestamp='2026-07-19T00:00:00+00:00',
            pytest_version='9',
            plugin_version='0.1.0',
            commit_sha=None,
        ),
        scenarios=[],
        stories=[],
        glossary=None,
    )
    html = render_diagrams_html(report, layout_stories(report))
    assert 'No stories were recorded' in html


def test_label_lines_wraps_near_midpoint() -> None:
    assert label_lines('Booking') == ['Booking']
    assert label_lines('unbreakable-very-long-identifier') == [
        'unbreakable-very-long-identifier'
    ]
    assert label_lines('group trip payment confirmation') == [
        'group trip payment',
        'confirmation',
    ]
