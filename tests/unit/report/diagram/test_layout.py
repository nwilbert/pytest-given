import math

import pytest

from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    Glossary,
    Story,
    StoryId,
    TermId,
)
from pytest_given.report.diagram import (
    DiagramEdge,
    DiagramGraph,
    DiagramLayout,
    DiagramNode,
    build_graph,
    count_crossings,
    layout_graph,
)
from pytest_given.report.diagram.layout import (
    LABEL_H,
    LABEL_OFFSET,
    MARGIN,
    MIN_NODE_DIST,
    NODE_HALF_H,
    NODE_HALF_W,
    LabelBox,
    _numbered_sequence,
    _sequence_spread,
    _slide_label,
    position_nodes,
)


def test_deterministic(trip_story: Story, trip_glossary: Glossary) -> None:
    graph = build_graph(trip_story, trip_glossary)
    assert position_nodes(graph) == position_nodes(graph)


def test_all_nodes_inside_canvas(trip_story: Story, trip_glossary: Glossary) -> None:
    graph = build_graph(trip_story, trip_glossary)
    positions, width, height = position_nodes(graph)
    for x_pos, y_pos in positions.values():
        assert MARGIN <= x_pos <= width - MARGIN
        assert MARGIN <= y_pos <= height - MARGIN


def test_minimum_pairwise_distance(trip_story: Story, trip_glossary: Glossary) -> None:
    graph = build_graph(trip_story, trip_glossary)
    positions, _width, _height = position_nodes(graph)
    coords = list(positions.values())
    for index, (first_x, first_y) in enumerate(coords):
        for second_x, second_y in coords[index + 1 :]:
            # The grid places every node on a distinct column/row cell whose
            # spacing is >= MIN_NODE_DIST, so no two nodes can overlap.
            assert (
                math.hypot(second_x - first_x, second_y - first_y)
                >= MIN_NODE_DIST - 1e-6
            )


def test_no_edge_crossings(trip_story: Story, trip_glossary: Glossary) -> None:
    """The overriding layout rule: drawn arrows must not overlap. On this
    story (which is planar) the crossing-minimizing placement reaches zero."""
    graph = build_graph(trip_story, trip_glossary)
    layout = layout_graph(graph)
    assert count_crossings(layout.edges) == 0


def _actor(node_id: str) -> DiagramNode:
    return DiagramNode(
        id=node_id, label=node_id, sublabel=None, glyph='actor', term_id=None
    )


def _work(node_id: str) -> DiagramNode:
    return DiagramNode(
        id=node_id, label=node_id, sublabel=None, glyph='work', term_id=None
    )


def _edge(source: str, target: str, number: int | None = 1) -> DiagramEdge:
    return DiagramEdge(
        source=source,
        target=target,
        label='does',
        activity_id=ActivityId(number or 1),
        number=number,
        connective=False,
    )


def test_disjoint_stars_do_not_cross_and_keep_min_distance() -> None:
    """Three independent actor->work pairs: a planar graph the layout must
    place with neither crossings nor overlapping nodes, growing the canvas
    to fit."""
    nodes = tuple(
        [_actor(f'actor:{index}') for index in range(3)]
        + [_work(f'work:{index}') for index in range(3)]
    )
    edges = tuple(
        _edge(f'actor:{index}', f'work:{index}', number=index + 1) for index in range(3)
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    positions, _width, _height = position_nodes(graph)
    coords = list(positions.values())
    for index, (first_x, first_y) in enumerate(coords):
        for second_x, second_y in coords[index + 1 :]:
            assert math.hypot(second_x - first_x, second_y - first_y) >= MIN_NODE_DIST
    assert count_crossings(layout_graph(graph).edges) == 0


def _sequence_spread_of(layout: DiagramLayout) -> float:
    positions = {placed.node.id: (placed.x, placed.y) for placed in layout.nodes}
    return _sequence_spread(_numbered_sequence(layout.graph), positions)


def test_sequence_term_pulls_numbered_steps_together(
    trip_story: Story, trip_glossary: Glossary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The secondary goal: consecutively numbered activities sit near each
    other. Turning the sequence weight off must not produce a tighter reading
    order than leaving it on -- and it must never cost a crossing."""
    from pytest_given.report.diagram import layout as layout_module

    graph = build_graph(trip_story, trip_glossary)
    with_sequence = layout_graph(graph)

    monkeypatch.setattr(layout_module, 'SEQUENCE_COST', 0.0)
    without_sequence = layout_graph(graph)

    assert _sequence_spread_of(with_sequence) <= _sequence_spread_of(without_sequence)
    assert count_crossings(with_sequence.edges) == 0


def test_hub_fan_has_no_crossings() -> None:
    """A single actor connected to many work objects (a star) is always
    planar; every fan edge must stay clear of the others."""
    nodes = tuple(
        [_actor('actor:hub')] + [_work(f'work:{index}') for index in range(5)]
    )
    edges = tuple(
        _edge('actor:hub', f'work:{index}', number=index + 1) for index in range(5)
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    assert count_crossings(layout_graph(graph).edges) == 0


def test_single_actor_no_edges_lands_on_canvas_centre() -> None:
    graph = DiagramGraph(
        story_id=StoryId('s'), title='S', nodes=(_actor('actor:only'),), edges=()
    )
    positions, width, height = position_nodes(graph)
    assert positions['actor:only'] == (width / 2, height / 2)


def test_isolated_work_object_lands_on_canvas_centre() -> None:
    """A work node with no edges has no layering pull; it falls at the centre
    of the minimum canvas rather than crashing on an empty layout."""
    graph = DiagramGraph(
        story_id=StoryId('s'), title='S', nodes=(_work('work:solo'),), edges=()
    )
    positions, width, height = position_nodes(graph)
    assert positions['work:solo'] == (width / 2, height / 2)


def test_empty_graph_returns_minimum_canvas() -> None:
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=(), edges=())
    positions, width, height = position_nodes(graph)
    assert positions == {}
    assert width > 0.0
    assert height > 0.0


def test_self_loop_exerts_no_force_and_stays_deterministic() -> None:
    nodes = (_actor('actor:looper'), _work('work:w'))
    edges = (
        _edge('actor:looper', 'actor:looper'),
        _edge('actor:looper', 'work:w', number=2),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    assert position_nodes(graph) == position_nodes(graph)


def test_directed_cycle_across_work_objects_still_layers() -> None:
    """Two activities that point work objects back at each other form a
    directed cycle; layering must break it rather than loop forever."""
    nodes = (_work('work:a'), _work('work:b'))
    edges = (
        _edge('work:a', 'work:b', number=1),
        _edge('work:b', 'work:a', number=2),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    positions, _width, _height = position_nodes(graph)
    assert set(positions) == {'work:a', 'work:b'}


def _boxes_overlap(a: LabelBox, b: LabelBox) -> bool:
    return not (
        a.x + a.width <= b.x
        or b.x + b.width <= a.x
        or a.y + a.height <= b.y
        or b.y + b.height <= a.y
    )


def _perpendicular_distance(
    point_x: float, point_y: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Distance from a point to the infinite line through (x1, y1) and
    (x2, y2). Trimming an edge only moves its endpoints along the same
    line, so the trimmed segment's line is also the untrimmed edge's line."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    assert length > 0.0, 'coincident edge endpoints have no defined line'
    return abs((point_x - x1) * dy - (point_y - y1) * dx) / length


def test_layout_graph_deterministic(trip_story: Story, trip_glossary: Glossary) -> None:
    graph = build_graph(trip_story, trip_glossary)
    assert layout_graph(graph) == layout_graph(graph)


def test_labels_do_not_overlap_labels_or_nodes(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    layout = layout_graph(graph)
    node_boxes = [
        LabelBox(
            x=p.x - NODE_HALF_W,
            y=p.y - NODE_HALF_H,
            width=2 * NODE_HALF_W,
            height=2 * NODE_HALF_H,
        )
        for p in layout.nodes
    ]
    label_boxes = [e.label for e in layout.edges]
    for index, box in enumerate(label_boxes):
        for other in label_boxes[index + 1 :]:
            assert not _boxes_overlap(box, other)
        for node_box in node_boxes:
            assert not _boxes_overlap(box, node_box)


def test_trimmed_endpoints_leave_visible_edges(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    layout = layout_graph(graph)
    for placed in layout.edges:
        if not placed.loop:
            assert math.hypot(placed.x2 - placed.x1, placed.y2 - placed.y1) >= 40.0


def test_labels_sit_near_their_edges(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    """Regression test for the 120px brute-force LABEL_OFFSET: a label must
    sit close to the edge it names, not off in space avoiding collisions at
    any cost."""
    graph = build_graph(trip_story, trip_glossary)
    layout = layout_graph(graph)
    for placed in layout.edges:
        if placed.loop:
            continue
        centre_x = placed.label.x + placed.label.width / 2
        centre_y = placed.label.y + placed.label.height / 2
        distance = _perpendicular_distance(
            centre_x, centre_y, placed.x1, placed.y1, placed.x2, placed.y2
        )
        assert distance <= LABEL_OFFSET + LABEL_H


def test_duplicate_first_step_drawn_once(trip_glossary: Glossary) -> None:
    """A two-path activity whose paths share an identical first step must draw
    that arrow only once -- two coincident arrows are overlapping lines."""

    def term_ref(term_id: str, display: str) -> ActivityTermRef:
        return ActivityTermRef(term_id=TermId(term_id), display=display)

    story = Story(
        id=StoryId('dup'),
        title='Dup',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            term_ref('booking-system', 'Booking System'),
                            term_ref('send', 'sends'),
                            term_ref('confirmation', 'Confirmation'),
                            term_ref('add', 'to'),
                            term_ref('guest', 'Alice'),
                        )
                    ),
                    ActivityPath(
                        parts=(
                            term_ref('booking-system', 'Booking System'),
                            term_ref('send', 'sends'),
                            term_ref('confirmation', 'Confirmation'),
                            term_ref('add', 'to'),
                            term_ref('guest', 'Bob'),
                        )
                    ),
                ),
            ),
        ),
    )
    graph = build_graph(story, trip_glossary)
    layout = layout_graph(graph)
    sends_edges = [placed for placed in layout.edges if placed.edge.label == 'sends']
    assert len(sends_edges) == 1
    assert count_crossings(layout.edges) == 0


def test_self_loop_marked_and_label_above_node(trip_glossary: Glossary) -> None:
    def term_ref(term_id: str, display: str) -> ActivityTermRef:
        return ActivityTermRef(term_id=TermId(term_id), display=display)

    story = Story(
        id=StoryId('loop'),
        title='Loop',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            term_ref('organizer', 'Carol'),
                            term_ref('add', 'checks'),
                            term_ref('organizer', 'Carol'),
                        )
                    ),
                ),
            ),
        ),
    )
    graph = build_graph(story, trip_glossary)
    layout = layout_graph(graph)
    assert len(layout.nodes) == 1
    placed = layout.edges[0]
    node = layout.nodes[0]
    assert placed.loop is True
    assert placed.label.y + placed.label.height <= node.y - NODE_HALF_H


def test_slide_label_falls_back_to_least_overlapping_candidate() -> None:
    """When every slide/offset/side combination still overlaps an obstacle
    (here, one the size of the whole canvas), `_slide_label` must fall back
    to the best candidate seen rather than returning None."""
    edge = _edge('a', 'b')
    unavoidable_obstacle = LabelBox(
        x=-1_000_000.0, y=-1_000_000.0, width=2_000_000.0, height=2_000_000.0
    )
    label = _slide_label(edge, 0.0, 0.0, 100.0, 0.0, 1.0, 0.0, [unavoidable_obstacle])
    assert isinstance(label, LabelBox)
