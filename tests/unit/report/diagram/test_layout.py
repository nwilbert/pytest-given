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
    LabelBox,
    _actor_fans,
    _clockwise_disorder,
    _min_pair_distance,
    _numbered_sequence,
    _orient_start_top_left,
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


def _edge(source: str, target: str, number: int | None = 1) -> DiagramEdge:
    return DiagramEdge(
        source=source,
        target=target,
        label='does',
        activity_id=ActivityId(number or 1),
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

    nodes = tuple(
        [_actor('a:root')] + [_work(f'w:{index}') for index in range(1, 6)]
    )
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
        _actor('a:0'), _actor('a:1'),
        _work('w:0'), _work('w:1'), _work('w:2'),
        _work('w:3'), _work('w:4'), _work('w:5'),
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
    # seeds are genuinely non-planar; a forced-crossing warning is expected
    # here and is not the property under test (the dedicated K5 test above
    # asserts the warning itself). Silence it so it doesn't pollute the run.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for seed in range(100):
            rng = random.Random(seed)
            graph = _random_story_graph(rng)
            positions, width, height = position_nodes(graph)
            assert position_nodes(graph) == (positions, width, height)  # deterministic
            coords = list(positions.values())
            for index, (fx, fy) in enumerate(coords):
                assert MARGIN <= fx <= width - MARGIN
                assert MARGIN <= fy <= height - MARGIN
                for sx, sy in coords[index + 1 :]:
                    assert math.hypot(sx - fx, sy - fy) >= MIN_NODE_DIST - 1e-6
            # layout_graph exercises the edge/label passes too (must not raise).
            layout_graph(graph)


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
