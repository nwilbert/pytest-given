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
    DiagramNode,
    build_graph,
    layout_graph,
)
from pytest_given.report.diagram.layout import (
    BAND_X_LEFT,
    BAND_X_RIGHT_INSET,
    LABEL_H,
    LABEL_OFFSET,
    MARGIN,
    MIN_NODE_DIST,
    NODE_HALF_H,
    NODE_HALF_W,
    LabelBox,
    _slide_label,
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
    for x_pos, y_pos in positions.values():
        assert MARGIN <= x_pos <= width - MARGIN
        assert MARGIN <= y_pos <= height - MARGIN


def test_minimum_pairwise_distance(trip_story: Story, trip_glossary: Glossary) -> None:
    import math

    graph = build_graph(trip_story, trip_glossary)
    positions, _width, _height = position_nodes(graph)
    coords = list(positions.values())
    for index, (first_x, first_y) in enumerate(coords):
        for second_x, second_y in coords[index + 1 :]:
            # The post-relaxation separation pass guarantees MIN_NODE_DIST
            # for every pair (a tiny floating-point epsilon covers the ring
            # search's trig rounding, not a loosened invariant).
            assert (
                math.hypot(second_x - first_x, second_y - first_y)
                >= MIN_NODE_DIST - 1e-6
            )


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


def test_three_initiators_keep_min_distance_and_canvas_grows() -> None:
    import math

    nodes = tuple(
        [_actor(f'actor:{index}') for index in range(3)]
        + [_work(f'work:{index}') for index in range(3)]
    )
    edges = tuple(
        _edge(f'actor:{index}', f'work:{index}', number=index + 1) for index in range(3)
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    positions, _width, height = position_nodes(graph)
    assert height > 620.0
    actor_coords = [positions[f'actor:{index}'] for index in range(3)]
    for index, (first_x, first_y) in enumerate(actor_coords):
        for second_x, second_y in actor_coords[index + 1 :]:
            assert math.hypot(second_x - first_x, second_y - first_y) >= MIN_NODE_DIST


def test_single_actor_no_edges_lands_on_right_band() -> None:
    graph = DiagramGraph(
        story_id=StoryId('s'), title='S', nodes=(_actor('actor:only'),), edges=()
    )
    positions, width, height = position_nodes(graph)
    assert positions['actor:only'] == (width - BAND_X_RIGHT_INSET, height / 2)


def test_satellite_fan_spreads_multiple_satellites() -> None:
    import math

    nodes = tuple(
        [_actor('actor:hub')] + [_work(f'work:{index}') for index in range(3)]
    )
    edges = tuple(_edge('actor:hub', f'work:{index}') for index in range(3))
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    positions, _width, _height = position_nodes(graph)
    satellite_coords = [positions[f'work:{index}'] for index in range(3)]
    for index, (first_x, first_y) in enumerate(satellite_coords):
        for second_x, second_y in satellite_coords[index + 1 :]:
            assert math.hypot(second_x - first_x, second_y - first_y) >= 150.0


def test_self_loop_exerts_no_force_and_stays_deterministic() -> None:
    nodes = (_actor('actor:looper'), _work('work:w'))
    edges = (
        _edge('actor:looper', 'actor:looper'),
        _edge('actor:looper', 'work:w', number=2),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    assert position_nodes(graph) == position_nodes(graph)


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
    import math

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
    import math

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


def test_isolated_work_object_seeds_at_canvas_centre() -> None:
    """A work node with no placed neighbour (no edges at all) falls back to
    the canvas centre in `_seed_work_objects`, rather than crashing on an
    empty mean over `placed_ids`."""
    graph = DiagramGraph(
        story_id=StoryId('s'), title='S', nodes=(_work('work:solo'),), edges=()
    )
    positions, width, height = position_nodes(graph)
    assert positions['work:solo'] == (width / 2, height / 2)


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
