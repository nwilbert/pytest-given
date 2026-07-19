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
    MARGIN,
    MIN_NODE_DIST,
    NODE_HALF_H,
    NODE_HALF_W,
    LabelBox,
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


def test_minimum_pairwise_distance(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    import math

    graph = build_graph(trip_story, trip_glossary)
    positions, _width, _height = position_nodes(graph)
    coords = list(positions.values())
    for index, (first_x, first_y) in enumerate(coords):
        for second_x, second_y in coords[index + 1 :]:
            # Looser floor than MIN_NODE_DIST: clamping at the margins may
            # legitimately compress below the relaxation target.
            assert math.hypot(second_x - first_x, second_y - first_y) >= 100.0


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
        source=source, target=target, label='does',
        activity_id=ActivityId(number or 1), number=number, connective=False,
    )


def test_three_initiators_keep_min_distance_and_canvas_grows() -> None:
    import math

    nodes = tuple(
        [_actor(f'actor:{index}') for index in range(3)]
        + [_work(f'work:{index}') for index in range(3)]
    )
    edges = tuple(
        _edge(f'actor:{index}', f'work:{index}', number=index + 1)
        for index in range(3)
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
        a.x + a.width <= b.x or b.x + b.width <= a.x
        or a.y + a.height <= b.y or b.y + b.height <= a.y
    )


def test_layout_graph_deterministic(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    assert layout_graph(graph) == layout_graph(graph)


def test_labels_do_not_overlap_labels_or_nodes(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    layout = layout_graph(graph)
    node_boxes = [
        LabelBox(x=p.x - NODE_HALF_W, y=p.y - NODE_HALF_H,
                 width=2 * NODE_HALF_W, height=2 * NODE_HALF_H)
        for p in layout.nodes
    ]
    label_boxes = [e.label for e in layout.edges]
    for i, box in enumerate(label_boxes):
        for other in label_boxes[i + 1 :]:
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


def test_self_loop_marked_and_label_above_node(trip_glossary: Glossary) -> None:
    def term_ref(term_id: str, display: str) -> ActivityTermRef:
        return ActivityTermRef(term_id=TermId(term_id), display=display)

    story = Story(
        id=StoryId('loop'), title='Loop',
        activities=(
            Activity(id=ActivityId(1), paths=(
                ActivityPath(parts=(
                    term_ref('organizer', 'Carol'), term_ref('add', 'checks'),
                    term_ref('organizer', 'Carol'),
                )),
            )),
        ),
    )
    graph = build_graph(story, trip_glossary)
    layout = layout_graph(graph)
    assert len(layout.nodes) == 1
    placed = layout.edges[0]
    node = layout.nodes[0]
    assert placed.loop is True
    assert placed.label.y + placed.label.height <= node.y - NODE_HALF_H
