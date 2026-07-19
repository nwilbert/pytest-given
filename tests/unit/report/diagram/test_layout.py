from pytest_given.model import Glossary, Story
from pytest_given.report.diagram import build_graph
from pytest_given.report.diagram.layout import (
    BAND_X_LEFT,
    MARGIN,
    position_nodes,
)


def test_initiators_left_recipients_right(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    positions, width, _height = position_nodes(graph)
    by_label = {n.label: n for n in graph.nodes if n.glyph == 'actor'}
    carol_x = positions[by_label['Carol'].id][0]
    system_x = positions[by_label['Booking System'].id][0]
    alice_x = positions[by_label['Alice'].id][0]
    bob_x = positions[by_label['Bob'].id][0]
    assert carol_x == BAND_X_LEFT
    assert system_x == BAND_X_LEFT
    assert alice_x > width / 2
    assert bob_x > width / 2
    # Recipients ordered by first appearance: Alice (activity 1) above Bob.
    assert positions[by_label['Alice'].id][1] < positions[by_label['Bob'].id][1]


def test_deterministic(trip_story: Story, trip_glossary: Glossary) -> None:
    graph = build_graph(trip_story, trip_glossary)
    assert position_nodes(graph) == position_nodes(graph)


def test_all_nodes_inside_canvas(trip_story: Story, trip_glossary: Glossary) -> None:
    graph = build_graph(trip_story, trip_glossary)
    positions, width, height = position_nodes(graph)
    for x, y in positions.values():
        assert MARGIN <= x <= width - MARGIN
        assert MARGIN <= y <= height - MARGIN


def test_minimum_pairwise_distance(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    import math

    graph = build_graph(trip_story, trip_glossary)
    positions, _width, _height = position_nodes(graph)
    coords = list(positions.values())
    for i, (ax, ay) in enumerate(coords):
        for bx, by in coords[i + 1 :]:
            # Looser floor than MIN_NODE_DIST: clamping at the margins may
            # legitimately compress below the relaxation target.
            assert math.hypot(bx - ax, by - ay) >= 100.0
