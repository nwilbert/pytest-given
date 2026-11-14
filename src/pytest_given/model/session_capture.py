"""What one session captured, before a report is built from it — the payload a
pytest-xdist worker sends the main process. Never part of `ReportData`."""

from collections.abc import Sequence
from dataclasses import dataclass

from .schema import Glossary, NodeId, Scenario, Story, StoryId


@dataclass(frozen=True, kw_only=True)
class SessionCapture:
    """`scenarios` are grouped but not yet in report order; `collection_index`
    holds each one's position as collected, for the order's last tie-break.
    """

    scenarios: list[Scenario]
    collection_index: dict[NodeId, int]
    stories: list[Story]
    glossary: Glossary | None


def merge_captures(captures: Sequence[SessionCapture]) -> SessionCapture:
    """Every pytest-xdist worker collects the whole suite, so each holds the
    same stories and glossary; the scenarios are each worker's own."""
    stories: dict[StoryId, Story] = {}
    for capture in captures:
        for story in capture.stories:
            stories.setdefault(story.id, story)
    return SessionCapture(
        scenarios=[scenario for capture in captures for scenario in capture.scenarios],
        collection_index={
            node_id: index
            for capture in captures
            for node_id, index in capture.collection_index.items()
        },
        stories=list(stories.values()),
        glossary=captures[0].glossary if captures else None,
    )
