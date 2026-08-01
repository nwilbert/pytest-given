import itertools
import math
import random

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
    PREFERRED_DIST,
    LabelBox,
    _actor_fans,
    _clockwise_disorder,
    _min_pair_distance,
    _numbered_sequence,
    _orient_start_top_left,
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
            # Construction seats every node at least MIN_NODE_DIST from all others.
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


def _edge(
    source: str,
    target: str,
    number: int | None = 1,
    activity_id: int | None = None,
) -> DiagramEdge:
    return DiagramEdge(
        source=source,
        target=target,
        label='does',
        activity_id=ActivityId(
            activity_id if activity_id is not None else (number or 1)
        ),
        number=number,
        connective=False,
    )


def test_construction_adds_activities_in_numbered_order() -> None:
    """The seed walks activities 1..N: an earlier activity's newly introduced
    node is placed before a later activity's, so the reading order structures
    the layout instead of being recovered afterwards."""
    from pytest_given.report.diagram.layout import _construction_order

    nodes = (_actor('a:hub'), _work('w:1'), _work('w:2'), _work('w:3'))
    edges = (
        _edge('a:hub', 'w:3', number=3),
        _edge('a:hub', 'w:1', number=1),
        _edge('a:hub', 'w:2', number=2),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    order = _construction_order(graph)
    # Edges come out in ascending activity number regardless of edge order.
    assert order == [
        ('a:hub', 'w:1', True),
        ('a:hub', 'w:2', True),
        ('a:hub', 'w:3', True),
    ]


def test_seed_is_crossing_free_and_spaced_on_a_tree() -> None:
    from pytest_given.report.diagram.layout import _construct_seed, _count_overlaps

    nodes = tuple([_actor('a:root')] + [_work(f'w:{index}') for index in range(1, 6)])
    edges = (
        _edge('a:root', 'w:1', number=1),
        _edge('w:1', 'w:2', number=2),
        _edge('a:root', 'w:3', number=3),
        _edge('w:3', 'w:4', number=4),
        _edge('a:root', 'w:5', number=5),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    seed = _construct_seed(graph)
    directed = [(e.source, e.target) for e in edges]
    segments = [(seed[s], seed[t], s, t) for s, t in directed]
    assert _count_overlaps(segments) == 0
    assert _min_pair_distance(seed) >= MIN_NODE_DIST - 1e-6


def test_snap_alignment_pulls_near_coordinates_onto_a_shared_line() -> None:
    """Two connected nodes whose y-coordinates already nearly agree are pulled
    onto one horizontal line, so the edge reads as an intentional straight run."""
    from pytest_given.report.diagram.layout import _snap_alignment

    nodes = (_actor('a'), _work('b'))
    edges = (_edge('a', 'b', number=1),)
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    refined = {'a': (0.0, 0.0), 'b': (300.0, 20.0)}
    snapped = _snap_alignment(refined, graph)
    assert snapped['a'][1] == snapped['b'][1]  # shared row
    # x is untouched: the two nodes are far apart on that axis, no cluster.
    assert snapped['a'][0] == 0.0
    assert snapped['b'][0] == 300.0


def test_snap_alignment_rejects_a_snap_that_would_crowd_nodes() -> None:
    """A snap is applied only when it keeps the hard invariant. Here b and c have
    almost-equal x but sit only just past the minimum node distance apart, so
    folding either onto their shared column would pull them below it -- the snap
    is refused and both keep their solved positions."""
    from pytest_given.report.diagram.layout import _snap_alignment

    nodes = (_actor('a'), _work('b'), _work('c'))
    edges = (_edge('a', 'b', number=1),)
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    refined = {'a': (0.0, 0.0), 'b': (300.0, 0.0), 'c': (322.0, 249.5)}
    snapped = _snap_alignment(refined, graph)
    assert snapped['b'] == (300.0, 0.0)
    assert snapped['c'] == (322.0, 249.5)


def test_construction_seats_a_closing_triangle_crossing_free() -> None:
    """a:helper is placed anchored to a:root (activity 1); w:mid is placed
    anchored to a:root (activity 2), but w:mid *also* closes back to
    a:helper (activity 3) -- an edge between two nodes that, without the
    lookahead in _place_new_node, would already both be fixed by the time
    that third edge is drawn. This exercises the branch of the lookahead
    where the not-yet-placed node is the *target* of the later closing edge
    (a:helper is the later edge's source, w:mid its target)."""
    from pytest_given.report.diagram.layout import _construct_seed, _count_overlaps

    nodes = (_actor('a:root'), _actor('a:helper'), _work('w:mid'))
    edges = (
        _edge('a:root', 'a:helper', number=1),
        _edge('a:root', 'w:mid', number=2),
        _edge('a:helper', 'w:mid', number=3),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    seed = _construct_seed(graph)
    directed = [(e.source, e.target) for e in edges]
    segments = [(seed[s], seed[t], s, t) for s, t in directed]
    assert _count_overlaps(segments) == 0
    assert _min_pair_distance(seed) >= MIN_NODE_DIST - 1e-6


def test_construction_seats_a_node_reaching_two_prior_anchors_crossing_free() -> None:
    """A multi-path activity whose object fans out to several already-placed
    recipients: a:root reaches a:one (activity 1) and a:two (activity 2), then
    w:hub is placed (activity 3, anchored to a:root) but *also* closes back to
    both a:one (activity 4) and a:two (activity 5) -- two closing edges onto
    two nodes that are already fixed when w:hub is seated. The generalized
    lookahead must fold *both* into w:hub's placement so neither closing edge
    forces a crossing (the single-partner lookahead would only guard one)."""
    from pytest_given.report.diagram.layout import _construct_seed, _count_overlaps

    nodes = (_actor('a:root'), _actor('a:one'), _actor('a:two'), _work('w:hub'))
    edges = (
        _edge('a:root', 'a:one', number=1),
        _edge('a:root', 'a:two', number=2),
        _edge('a:root', 'w:hub', number=3),
        _edge('w:hub', 'a:one', number=4),
        _edge('w:hub', 'a:two', number=5),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    seed = _construct_seed(graph)
    directed = [(e.source, e.target) for e in edges]
    segments = [(seed[s], seed[t], s, t) for s, t in directed]
    assert _count_overlaps(segments) == 0
    assert _min_pair_distance(seed) >= MIN_NODE_DIST - 1e-6


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
    """Total gap, in PREFERRED_DIST-widths, between the midpoints of
    consecutively numbered activity edges -- lower means the numbered steps line
    up tighter in reading order. A test-only readability metric."""
    positions = {placed.node.id: (placed.x, placed.y) for placed in layout.nodes}
    midpoints = [
        (
            (positions[source][0] + positions[target][0]) / 2,
            (positions[source][1] + positions[target][1]) / 2,
        )
        for source, target in _numbered_sequence(layout.graph)
    ]
    return sum(
        math.hypot(later[0] - earlier[0], later[1] - earlier[1]) / PREFERRED_DIST
        for earlier, later in itertools.pairwise(midpoints)
    )


def test_sequence_term_pulls_numbered_steps_together(
    trip_story: Story, trip_glossary: Glossary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The secondary goal: consecutively numbered activities sit near each
    other. Turning the sequence weight off must not produce a tighter reading
    order than leaving it on -- and it must never cost a crossing."""
    from pytest_given.report.diagram import layout as layout_module

    graph = build_graph(trip_story, trip_glossary)
    with_sequence = layout_graph(graph)

    monkeypatch.setattr(layout_module, 'SEQUENCE_K', 0.0)
    without_sequence = layout_graph(graph)

    assert _sequence_spread_of(with_sequence) <= _sequence_spread_of(without_sequence)
    assert count_crossings(with_sequence.edges) == 0


def test_story_start_seated_top_left(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    """Third priority: the story's start node (activity 1's initiator) is seated
    as near the top-left as an axis-aligned reflection can put it -- and that
    reflection, being an isometry, leaves the diagram crossing-free."""
    graph = build_graph(trip_story, trip_glossary)
    layout = layout_graph(graph)
    positions = {placed.node.id: (placed.x, placed.y) for placed in layout.nodes}
    start = _numbered_sequence(graph)[0][0]
    start_x, start_y = positions[start]
    width, height = layout.width, layout.height
    corner_distance = start_x + start_y
    for reflected_x, reflected_y in (
        (width - start_x, start_y),
        (start_x, height - start_y),
        (width - start_x, height - start_y),
    ):
        assert corner_distance <= reflected_x + reflected_y + 1e-6
    assert count_crossings(layout.edges) == 0


def test_reflection_prefers_clockwise_when_start_corner_ties() -> None:
    """A single-axis reflection flips handedness, so seating the start top-left
    could silently turn a clockwise fan counter-clockwise. When the start node
    is centred (all four reflections tie on start-corner distance), the
    clockwise-aware choice must break the tie toward the clockwise arrangement.
    """
    width = height = 800.0
    # Hub at the exact centre; its fan reads counter-clockwise as laid out
    # (north -> west -> south), so the identity frame has disorder 2.
    positions = {
        'h': (400.0, 400.0),
        't1': (400.0, 200.0),
        't2': (200.0, 400.0),
        't3': (400.0, 600.0),
    }
    fans = [('h', ('t1', 't2', 't3'))]
    assert _clockwise_disorder(fans, positions) == 2.0
    oriented = _orient_start_top_left(positions, width, height, 'h', fans)
    assert _clockwise_disorder(fans, oriented) == 0.0


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


def test_hub_fan_lays_out_clockwise() -> None:
    # One actor initiating three single-step activities toward three work
    # objects. All arrangements are crossing-free; the clockwise term should
    # settle the fan into clockwise number order.
    nodes = (_actor('a:hub'), _work('w:1'), _work('w:2'), _work('w:3'))
    edges = (
        _edge('a:hub', 'w:1', number=1),
        _edge('a:hub', 'w:2', number=2),
        _edge('a:hub', 'w:3', number=3),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    layout = layout_graph(graph)
    assert count_crossings(layout.edges) == 0
    positions = {placed.node.id: (placed.x, placed.y) for placed in layout.nodes}
    assert _clockwise_disorder(_actor_fans(graph), positions) == 0.0


def test_construction_lays_two_fans_out_clockwise() -> None:
    """Clockwise ordering is enforced during construction, not by a tunable
    cost. Two hubs with interleaved-by-number spokes: the seed must grow both
    fans clockwise, so the total disorder is zero and nothing crosses."""
    nodes = (
        _actor('a:0'),
        _actor('a:1'),
        _work('w:0'),
        _work('w:1'),
        _work('w:2'),
        _work('w:3'),
        _work('w:4'),
        _work('w:5'),
    )
    edges = (
        _edge('a:0', 'w:1', number=1),
        _edge('a:1', 'w:0', number=2),
        _edge('a:0', 'w:5', number=3),
        _edge('a:1', 'w:2', number=4),
        _edge('a:0', 'w:4', number=5),
        _edge('a:1', 'w:3', number=6),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    layout = layout_graph(graph)
    positions = {p.node.id: (p.x, p.y) for p in layout.nodes}
    assert _clockwise_disorder(_actor_fans(graph), positions) == 0.0
    assert count_crossings(layout.edges) == 0


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


def test_clockwise_disorder_scores_turn_direction() -> None:
    # Actor at origin; spokes numbered 1,2,3 pointing E, S, W (screen coords,
    # y down) -- that is a clockwise sweep, so disorder is zero.
    fans = [('a', ('t1', 't2', 't3'))]
    clockwise = {'a': (0.0, 0.0), 't1': (1.0, 0.0), 't2': (0.0, 1.0), 't3': (-1.0, 0.0)}
    assert _clockwise_disorder(fans, clockwise) == 0.0

    # Reverse the order (E, N, W) -> each turn is counter-clockwise: 2 bad turns.
    counter = {'a': (0.0, 0.0), 't1': (1.0, 0.0), 't2': (0.0, -1.0), 't3': (-1.0, 0.0)}
    assert _clockwise_disorder(fans, counter) == 2.0

    # A fan with fewer than two spokes contributes nothing.
    assert _clockwise_disorder([('a', ('t1',))], clockwise) == 0.0


def test_actor_fans_group_numbered_spokes_by_initiating_actor() -> None:
    # Carol initiates 1 and 2 (a fan); Dan initiates only 3 (no fan).
    nodes = (
        _actor('a:carol'),
        _actor('a:dan'),
        _work('w:1'),
        _work('w:2'),
        _work('w:3'),
    )
    edges = (
        _edge('a:carol', 'w:1', number=1),
        _edge('a:carol', 'w:2', number=2),
        _edge('a:dan', 'w:3', number=3),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    assert _actor_fans(graph) == [('a:carol', ('w:1', 'w:2'))]


def test_actor_fans_sort_by_number_regardless_of_edge_order() -> None:
    # Edges arrive out of numeric order (explicit ids); the fan must still be
    # in ascending-number order, and actors ordered by their lowest number.
    nodes = (
        _actor('a:x'),
        _actor('a:y'),
        _work('w:5'),
        _work('w:2'),
        _work('w:8'),
        _work('w:1'),
    )
    edges = (
        _edge('a:x', 'w:5', number=5),
        _edge('a:y', 'w:1', number=1),
        _edge('a:x', 'w:2', number=2),
        _edge('a:x', 'w:8', number=8),
        _edge('a:y', 'w:1', number=3),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    # a:y owns numbers 1 and 3 (lowest = 1) -> comes first; a:x owns 2,5,8.
    assert _actor_fans(graph) == [
        ('a:y', ('w:1', 'w:1')),
        ('a:x', ('w:2', 'w:5', 'w:8')),
    ]


def _random_story_graph(rng: random.Random) -> DiagramGraph:
    """A domain-shaped random graph: a few actors, each initiating some
    single-step activities toward activity-local work objects, plus the
    occasional actor->actor handoff. Deterministic for a given rng."""
    actor_count = rng.randint(1, 4)
    actors = [_actor(f'a:{i}') for i in range(actor_count)]
    nodes: list[DiagramNode] = list(actors)
    edges: list[DiagramEdge] = []
    activity_count = rng.randint(1, 8)
    for number in range(1, activity_count + 1):
        source = rng.choice(actors).id
        if actor_count > 1 and rng.random() < 0.25:
            target = rng.choice([a.id for a in actors if a.id != source])
        else:
            work = _work(f'w:{number}')
            nodes.append(work)
            target = work.id
        edges.append(_edge(source, target, number=number))
    return DiagramGraph(
        story_id=StoryId('s'), title='S', nodes=tuple(nodes), edges=tuple(edges)
    )


def test_random_graphs_keep_layout_invariants() -> None:
    """The layout must never crash, must stay deterministic, and must keep the
    invariants (min node distance, all nodes inside the canvas) on many
    random domain-shaped graphs."""
    import warnings

    # These graphs are arbitrary (including actor->actor handoffs), so some
    # seeds are genuinely non-planar; a forced-crossing warning is expected on
    # those and is not the property under test (the dedicated K5 test above
    # asserts the warning itself). Rather than blanket-silence it, we record
    # warnings and assert the sharper property: a graph that drew *no* warning
    # must be perfectly crossing-free -- the invariant is only ever relaxed on a
    # genuinely non-planar seed, never silently.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        for seed in range(100):
            rng = random.Random(seed)
            graph = _random_story_graph(rng)
            warned_before = len(caught)
            positions, width, height = position_nodes(graph)
            assert position_nodes(graph) == (positions, width, height)  # deterministic
            coords = list(positions.values())
            for index, (fx, fy) in enumerate(coords):
                assert MARGIN <= fx <= width - MARGIN
                assert MARGIN <= fy <= height - MARGIN
                for sx, sy in coords[index + 1 :]:
                    assert math.hypot(sx - fx, sy - fy) >= MIN_NODE_DIST - 1e-6
            # layout_graph exercises the edge/label passes too (must not raise).
            layout = layout_graph(graph)
            if len(caught) == warned_before:  # this graph warned nowhere
                assert count_crossings(layout.edges) == 0


def _random_tree_graph(rng: random.Random) -> DiagramGraph:
    """A random rooted tree: one actor root, each new work object attached to
    an existing node. Trees are planar, so the layout must reach zero
    crossings. Kept small so the heuristic reliably attains the minimum."""
    root = _actor('a:root')
    nodes: list[DiagramNode] = [root]
    placed_ids = [root.id]
    edges: list[DiagramEdge] = []
    size = rng.randint(2, 7)
    for number in range(1, size + 1):
        parent = rng.choice(placed_ids)
        work = _work(f'w:{number}')
        nodes.append(work)
        placed_ids.append(work.id)
        edges.append(_edge(parent, work.id, number=number))
    return DiagramGraph(
        story_id=StoryId('s'), title='S', nodes=tuple(nodes), edges=tuple(edges)
    )


def test_random_trees_have_no_crossings() -> None:
    """A tree is planar; the crossing-minimizing layout must draw it with no
    overlapping edges."""
    for seed in range(100):
        rng = random.Random(seed)
        graph = _random_tree_graph(rng)
        assert count_crossings(layout_graph(graph).edges) == 0, f'seed {seed}'


def test_move_is_valid_gates_on_crossings_grazes_and_distance() -> None:
    from pytest_given.report.diagram.layout import (
        MIN_NODE_DIST,
        _grazes,
        _min_pair_distance,
        _move_is_valid,
    )

    # A clean two-edge fan: no crossings, no grazes, nodes far apart.
    positions = {
        'a': (0.0, 0.0),
        'b': (400.0, -100.0),
        'c': (400.0, 160.0),
    }
    directed = [('a', 'b'), ('a', 'c')]
    assert _min_pair_distance(positions) >= MIN_NODE_DIST
    assert _grazes(positions, directed) == 0
    assert _move_is_valid(positions, directed, base_crossings=0, base_grazes=0)

    # Push c onto the a->b segment: now a graze appears, so the gate rejects.
    grazed = {**positions, 'c': (200.0, 5.0)}
    assert _grazes(grazed, directed) >= 1
    assert not _move_is_valid(grazed, directed, base_crossings=0, base_grazes=0)

    # Two nodes closer than MIN_NODE_DIST: rejected on distance alone.
    close = {'a': (0.0, 0.0), 'b': (10.0, 0.0)}
    assert not _move_is_valid(close, [], base_crossings=0, base_grazes=0)

    # An X of two edges sharing no node: one crossing, no grazes, nodes far
    # apart. Rejected when the baseline tolerates none; accepted once the
    # baseline already allows that one crossing.
    crossed = {
        'p1': (0.0, 0.0),
        'p2': (400.0, 300.0),
        'p3': (0.0, 300.0),
        'p4': (400.0, 0.0),
    }
    crossed_directed = [('p1', 'p2'), ('p3', 'p4')]
    assert _min_pair_distance(crossed) >= MIN_NODE_DIST
    assert _grazes(crossed, crossed_directed) == 0
    assert not _move_is_valid(
        crossed, crossed_directed, base_crossings=0, base_grazes=0
    )
    assert _move_is_valid(crossed, crossed_directed, base_crossings=1, base_grazes=0)


def test_candidate_is_valid_rejects_a_seat_grazing_a_drawn_edge() -> None:
    """The incremental placement check rejects a seat that would run the new
    node over an existing edge, even when the seat clears every node: the new
    node itself grazes a drawn edge it is not an endpoint of."""
    import math

    from pytest_given.report.diagram.layout import COLLINEAR_DEG, _candidate_is_valid

    positions = {'p': (0.0, 0.0), 'q': (600.0, 0.0), 'anchor': (300.0, 500.0)}
    drawn = [('p', 'q')]
    drawn_segments = [(positions['p'], positions['q'], 'p', 'q')]
    cos_limit = math.cos(math.radians(COLLINEAR_DEG))
    # 'new' sits 30px above the middle of p->q (a graze, < NODE_ON_EDGE_CLEARANCE)
    # yet more than MIN_NODE_DIST from every node, and its own anchor edge does
    # not reach the drawn edge -- only the graze rule can reject it.
    grazing = (300.0, 30.0)
    assert not _candidate_is_valid(
        'new', grazing, [('anchor', 'new')], drawn, drawn_segments, positions, cos_limit
    )
    # Lifted clear of the edge, the same seat is accepted.
    clear = (300.0, 200.0)
    assert _candidate_is_valid(
        'new', clear, [('anchor', 'new')], drawn, drawn_segments, positions, cos_limit
    )


def test_candidate_is_valid_matches_move_is_valid_over_random_layouts() -> None:
    """`_candidate_is_valid` is the incremental gate the backtracking seed trusts
    for its zero-crossing guarantee: seating one new node keeps the layout valid
    exactly when re-running the full `_move_is_valid` over the whole layout would
    accept it. Pin that equivalence so a future edit to either check cannot
    silently start accepting a crossing/graze/overlap.

    Under the precondition every placement maintains -- all placed nodes already
    at least MIN_NODE_DIST apart -- adding a node can only *increase* crossing and
    graze counts, so the incremental "no new violation" check must agree with the
    full "no worse than baseline" check on every candidate. Bases are generated
    PROPERLY SPACED (respecting that precondition); the search is deterministic
    (fixed seed, bounded sample count)."""
    from pytest_given.report.diagram.layout import (
        COLLINEAR_DEG,
        _candidate_is_valid,
        _count_overlaps,
        _grazes,
        _move_is_valid,
    )

    cos_limit = math.cos(math.radians(COLLINEAR_DEG))
    rng = random.Random(20240725)

    def spaced_base(count: int) -> dict[str, tuple[float, float]]:
        """`count` node positions, each at least MIN_NODE_DIST from the others."""
        placed: dict[str, tuple[float, float]] = {}
        attempts = 0
        while len(placed) < count and attempts < 10000:
            attempts += 1
            point = (rng.uniform(0.0, 2000.0), rng.uniform(0.0, 2000.0))
            if all(
                math.hypot(point[0] - other_x, point[1] - other_y) >= MIN_NODE_DIST
                for other_x, other_y in placed.values()
            ):
                placed[f'p{len(placed)}'] = point
        return placed

    mismatches = 0
    exercised_accept = False
    exercised_reject = False
    for _ in range(400):
        positions = spaced_base(rng.randint(2, 6))
        ids = list(positions)
        drawn: list[tuple[str, str]] = []
        for _ in range(rng.randint(0, 5)):
            source, target = rng.sample(ids, 2)
            if (source, target) not in drawn and (target, source) not in drawn:
                drawn.append((source, target))

        new_id = 'NEW'
        candidate = (rng.uniform(0.0, 2000.0), rng.uniform(0.0, 2000.0))
        anchor = rng.choice(ids)
        others = rng.sample(
            [node_id for node_id in ids if node_id != anchor],
            rng.randint(0, min(2, len(ids) - 1)),
        )
        new_pairs = [(anchor, new_id), *((new_id, other) for other in others)]

        drawn_segments = [(positions[s], positions[t], s, t) for s, t in drawn]
        incremental = _candidate_is_valid(
            new_id, candidate, new_pairs, drawn, drawn_segments, positions, cos_limit
        )

        # Reference: the full gate with the baseline the construction code uses --
        # the current crossing/graze count of `drawn` (before the new edges).
        base_crossings = _count_overlaps(drawn_segments)
        base_grazes = _grazes(positions, drawn)
        full = _move_is_valid(
            {**positions, new_id: candidate},
            [*drawn, *new_pairs],
            base_crossings,
            base_grazes,
        )

        if incremental != full:
            mismatches += 1
        exercised_accept = exercised_accept or incremental
        exercised_reject = exercised_reject or not incremental

    assert mismatches == 0
    # The sweep must actually exercise both outcomes, else the equivalence is
    # only pinned on a trivial (all-accept or all-reject) sample.
    assert exercised_accept
    assert exercised_reject


def test_point_near_segment_handles_a_degenerate_segment() -> None:
    from pytest_given.report.diagram.layout import _point_near_segment

    # start == end: the "segment" is a point; distance is point-to-that-point.
    assert _point_near_segment((0.0, 0.0), (5.0, 5.0), (5.0, 5.0), 10.0) is True
    assert _point_near_segment((0.0, 0.0), (50.0, 50.0), (50.0, 50.0), 10.0) is False


def test_segment_distance_handles_a_degenerate_segment() -> None:
    from pytest_given.report.diagram.layout import _segment_distance

    assert _segment_distance((0.0, 0.0), (3.0, 4.0), (3.0, 4.0)) == 5.0


def test_refinement_never_increases_crossings_or_overlaps(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    from pytest_given.report.diagram.layout import (
        MIN_NODE_DIST,
        _construct_seed,
        _count_overlaps,
        _directed_edges,
        _min_pair_distance,
        _refine_forces,
    )

    graph = build_graph(trip_story, trip_glossary)
    seed = _construct_seed(graph)
    directed = _directed_edges(graph)
    seed_crossings = _count_overlaps([(seed[s], seed[t], s, t) for s, t in directed])
    refined = _refine_forces(seed, graph)
    refined_crossings = _count_overlaps(
        [(refined[s], refined[t], s, t) for s, t in directed]
    )
    assert refined_crossings <= seed_crossings
    assert _min_pair_distance(refined) >= MIN_NODE_DIST - 1e-6
    assert _refine_forces(seed, graph) == refined  # deterministic


def test_forced_crossing_on_a_nonplanar_closing_edge_is_surfaced() -> None:
    """K5 is non-planar: it has no crossing-free straight-line drawing at all.
    Every new-node edge is placed crossing-free, so a crossing can only come
    from a closing edge (both endpoints already placed). The layout surfaces
    that with a warning rather than silently claiming zero crossings."""
    nodes = tuple(_actor(f'n:{i}') for i in range(5))
    # All ten pairs among five nodes, numbered so construction closes the graph.
    pairs = [(a, b) for a in range(5) for b in range(a + 1, 5)]
    edges = tuple(
        _edge(f'n:{a}', f'n:{b}', number=index + 1)
        for index, (a, b) in enumerate(pairs)
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    with pytest.warns(UserWarning, match='non-planar'):
        position_nodes(graph)


def test_backtracking_seats_a_boxed_in_fan_crossing_free() -> None:
    """A guest fan seated wide apart with filler spokes boxing the canvas
    middle, then a work object anchored to a *separate* system node that fans
    back to BOTH guests -- the 'Book a Group Trip' shape. No single seat for
    the fanning object reaches both guests crossing-free, so the forward greedy
    walk relaxes one closing edge and draws a crossing; the backtracking seed
    re-seats the earlier nodes and reaches both. The seed must be crossing-free
    (no non-planar warning) and the full layout must have zero crossings."""
    import warnings

    nodes = (
        _actor('a:host'),
        _actor('a:alice'),
        _actor('a:bob'),
        _work('w:booking'),
        _actor('a:sys'),
        _work('w:notice'),
        _work('w:g0'),
        _work('w:g1'),
        _work('w:g2'),
    )
    edges = (
        _edge('a:host', 'a:alice', number=1),
        _edge('a:host', 'w:g0', number=2),
        _edge('a:host', 'w:g1', number=3),
        _edge('a:host', 'w:g2', number=4),
        _edge('a:host', 'a:bob', number=5),
        _edge('a:host', 'w:booking', number=6),
        _edge('a:sys', 'w:booking', number=7),
        _edge('a:sys', 'w:notice', number=8),
        _edge('w:notice', 'a:alice', number=None, activity_id=8),
        _edge('w:notice', 'a:bob', number=None, activity_id=8),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    with warnings.catch_warnings():
        warnings.simplefilter('error')  # backtracking must find zero crossings
        layout = layout_graph(graph)
    assert count_crossings(layout.edges) == 0


def test_backtracking_seed_is_deterministic() -> None:
    """The backtracking DFS is a fixed-order search with no RNG: the same graph
    must yield the identical seed on every call."""
    from pytest_given.report.diagram.layout import _construct_seed

    nodes = (
        _actor('a:host'),
        _actor('a:alice'),
        _actor('a:bob'),
        _work('w:booking'),
        _actor('a:sys'),
        _work('w:notice'),
        _work('w:g0'),
        _work('w:g1'),
        _work('w:g2'),
    )
    edges = (
        _edge('a:host', 'a:alice', number=1),
        _edge('a:host', 'w:g0', number=2),
        _edge('a:host', 'w:g1', number=3),
        _edge('a:host', 'w:g2', number=4),
        _edge('a:host', 'a:bob', number=5),
        _edge('a:host', 'w:booking', number=6),
        _edge('a:sys', 'w:booking', number=7),
        _edge('a:sys', 'w:notice', number=8),
        _edge('w:notice', 'a:alice', number=None, activity_id=8),
        _edge('w:notice', 'a:bob', number=None, activity_id=8),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    assert _construct_seed(graph) == _construct_seed(graph)


def test_seed_falls_back_to_greedy_when_placement_budget_exhausts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the placement budget forced to zero the DFS gives up immediately and
    returns the greedy fallback -- still a complete, valid layout (every node
    seated at least MIN_NODE_DIST from the others)."""
    from pytest_given.report.diagram import layout as layout_module
    from pytest_given.report.diagram.layout import _construct_seed

    monkeypatch.setattr(layout_module, 'MAX_SEED_PLACEMENTS', 0)
    # An extra edgeless node ('w:lonely') exercises the greedy fallback's
    # isolated-node placement, which never entered the construction walk.
    nodes = (
        _actor('a:host'),
        _actor('a:alice'),
        _actor('a:bob'),
        _work('w:booking'),
        _actor('a:sys'),
        _work('w:notice'),
        _work('w:g0'),
        _work('w:g1'),
        _work('w:g2'),
        _work('w:lonely'),
    )
    edges = (
        _edge('a:host', 'a:alice', number=1),
        _edge('a:host', 'w:g0', number=2),
        _edge('a:host', 'w:g1', number=3),
        _edge('a:host', 'w:g2', number=4),
        _edge('a:host', 'a:bob', number=5),
        _edge('a:host', 'w:booking', number=6),
        _edge('a:sys', 'w:booking', number=7),
        _edge('a:sys', 'w:notice', number=8),
        _edge('w:notice', 'a:alice', number=None, activity_id=8),
        _edge('w:notice', 'a:bob', number=None, activity_id=8),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')  # greedy fallback may surface the crossing
        seed = _construct_seed(graph)
    assert set(seed) == {node.id for node in nodes}
    assert _min_pair_distance(seed) >= MIN_NODE_DIST - 1e-6


def test_dfs_seed_places_an_isolated_node() -> None:
    """A node with no edges never enters the construction walk, so the DFS seats
    it in a trailing pass after the search completes (distinct from the greedy
    fallback's own isolated pass). On a small planar story the DFS solves well
    within budget, so this exercises that trailing pass on the DFS path: the
    isolated node must still be placed, at least MIN_NODE_DIST from every other."""
    from pytest_given.report.diagram.layout import _construct_seed

    nodes = (
        _actor('a:host'),
        _work('w:a'),
        _work('w:b'),
        _work('w:lonely'),
    )
    edges = (
        _edge('a:host', 'w:a', number=1),
        _edge('a:host', 'w:b', number=2),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    seed = _construct_seed(graph)
    assert set(seed) == {node.id for node in nodes}
    assert 'w:lonely' in seed
    assert _min_pair_distance(seed) >= MIN_NODE_DIST - 1e-6


def test_planar_story_never_warns(trip_story: Story, trip_glossary: Glossary) -> None:
    import warnings

    graph = build_graph(trip_story, trip_glossary)
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        position_nodes(graph)  # must not raise a warning-as-error


def test_refinement_tightens_a_three_spoke_fan_below_a_splay() -> None:
    """A preferred-distance potential settles a 3-spoke fan close together, not
    splayed to the maximum angle: the average spoke length stays near the
    preferred distance rather than blowing out."""
    from pytest_given.report.diagram.layout import (
        EDGE_REST_LENGTH,
        _construct_seed,
        _refine_forces,
    )

    nodes = (_actor('a:hub'), _work('w:1'), _work('w:2'), _work('w:3'))
    edges = (
        _edge('a:hub', 'w:1', number=1),
        _edge('a:hub', 'w:2', number=2),
        _edge('a:hub', 'w:3', number=3),
    )
    graph = DiagramGraph(story_id=StoryId('s'), title='S', nodes=nodes, edges=edges)
    refined = _refine_forces(_construct_seed(graph), graph)
    hub = refined['a:hub']
    for target in ('w:1', 'w:2', 'w:3'):
        length = math.hypot(refined[target][0] - hub[0], refined[target][1] - hub[1])
        assert length <= EDGE_REST_LENGTH * 1.6
