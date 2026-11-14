from pytest_given.model import (
    Glossary,
    NodeId,
    SessionCapture,
    Story,
    merge_captures,
)
from tests.unit.citation_reports import scenario_, story_


def _capture(
    node_ids: list[str],
    stories: list[Story] = [],  # noqa: B006 - never mutated
    glossary: Glossary | None = None,
) -> SessionCapture:
    return SessionCapture(
        scenarios=[scenario_(node_id) for node_id in node_ids],
        collection_index={NodeId(node_id): 7 for node_id in node_ids},
        stories=stories,
        glossary=glossary,
    )


def test_merging_keeps_every_capture_s_scenarios_and_their_index():
    merged = merge_captures([_capture(['a.py::t']), _capture(['b.py::t', 'c.py::t'])])
    assert [scenario.id for scenario in merged.scenarios] == [
        'a.py::t',
        'b.py::t',
        'c.py::t',
    ]
    assert merged.collection_index == {'a.py::t': 7, 'b.py::t': 7, 'c.py::t': 7}


def test_merging_keeps_one_story_per_id_the_first_capture_s():
    merged = merge_captures(
        [
            _capture([], [story_('s', 'First'), story_('u', 'Other')]),
            _capture([], [story_('s', 'Second'), story_('v', 'Last')]),
        ]
    )
    assert [(story.id, story.title) for story in merged.stories] == [
        ('s', 'First'),
        ('u', 'Other'),
        ('v', 'Last'),
    ]


def test_merging_takes_the_first_capture_s_glossary():
    first, second = Glossary(), Glossary()
    merged = merge_captures(
        [_capture([], glossary=first), _capture([], glossary=second)]
    )
    assert merged.glossary is first


def test_merging_no_capture_gives_an_empty_one():
    assert merge_captures([]) == SessionCapture(
        scenarios=[], collection_index={}, stories=[], glossary=None
    )
