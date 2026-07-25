"""Deterministic crossing-minimizing layout. Pure Python, no RNG.

The overriding rule is that drawn arrows must not overlap: no edge may cross
another edge, and (best effort) no edge may run over an unrelated node. Nodes
live at continuous (x, y) coordinates, never closer than MIN_NODE_DIST apart.
The seed is built by walking activities in ascending sequence-number order
(`_construction_order`) and seating each newly introduced node only at a
crossing-free position near its already-placed neighbour (`_construct_seed`,
`_place_new_node`, `_place_free_node`) -- a tree is planar, so this alone
reaches zero crossings on tree-shaped stories, and each actor's numbered
spokes are swept clockwise as they are added. A node that will later close
back onto an already-placed node (both its edges known at construction time,
e.g. a path's middle step) is seated with that future edge in mind too, so a
"closing" edge between two already-fixed nodes -- which would otherwise have
no placement freedom left -- stays crossing-free on real, planar stories.
Finally the whole diagram is
reflected (an isometry, so crossings and step spacing are untouched) to seat
the story's start node in the top-left corner -- the third priority. Edge
endpoints are trimmed back to the node rims and each edge's label is slid
along it until it clears every node and previously placed label.
"""

from __future__ import annotations

import itertools
import math
import warnings
from dataclasses import dataclass

from .graph import DiagramEdge, DiagramGraph, DiagramNode

MARGIN = 90.0
PAD = 180.0  # canvas padding around the outermost node centres
MIN_CANVAS_W = 1080.0
MIN_CANVAS_H = 620.0
MIN_NODE_DIST = 250.0  # hard floor: nodes never closer than this
PREFERRED_DIST = 300.0  # equilibrium spacing of the node pair-potential
EDGE_REST_LENGTH = 300.0  # spring rest length for a connected pair
INFLUENCE_RADIUS = 900.0  # beyond this, the pair-potential exerts no force
NODE_ON_EDGE_CLEARANCE = 70.0  # how near a segment a foreign node may sit

# Construction (Phase 1)
CONSTRUCT_RADIUS = 300.0  # first radius tried when seating a new node
CONSTRUCT_ANGLE_STEPS = 72  # candidate directions swept per radius (every 5deg)
RADIUS_GROWTH = 1.25  # radius multiplier when no direction is crossing-free
MAX_RADIUS_STEPS = 24  # growth attempts before the (near-unreachable) fallback
DEFAULT_DIRECTION = 0.0  # preferred first-spoke angle (east; y-down screen)

# Force refinement (Phase 2)
FORCE_ITERATIONS = 400
MAX_STEP = 60.0  # displacement cap per node per iteration (px)
SPRING_K = 0.10  # edge spring stiffness
REPULSION_K = 0.60  # short-range push below PREFERRED_DIST
ATTRACT_K = 0.02  # bounded long-range pull toward PREFERRED_DIST
SEQUENCE_K = 0.005  # gentle pull between consecutive numbered targets

NODE_HALF_W = 62.0
NODE_HALF_H = 58.0
TRIM_SOURCE = 56.0
TRIM_TARGET = 64.0
LABEL_CHAR_W = 7.0
LABEL_H = 20.0
BADGE_W = 30.0
LABEL_OFFSET = 18.0
LOOP_RADIUS = 46.0
# A label should sit clearly nearer its own arrow than any other, or it is
# ambiguous which step it names. This is how much closer (px) is "clearly".
LABEL_ASSOC_MARGIN = 46.0

COLLINEAR_DEG = 8.0  # two edges from a shared node this close in angle overlap


@dataclass(frozen=True, kw_only=True)
class PlacedNode:
    node: DiagramNode
    x: float
    y: float


@dataclass(frozen=True, kw_only=True)
class LabelBox:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, kw_only=True)
class PlacedEdge:
    edge: DiagramEdge
    x1: float
    y1: float
    x2: float
    y2: float
    loop: bool
    label: LabelBox


@dataclass(frozen=True, kw_only=True)
class DiagramLayout:
    graph: DiagramGraph
    nodes: tuple[PlacedNode, ...]
    edges: tuple[PlacedEdge, ...]
    width: float
    height: float


def position_nodes(
    graph: DiagramGraph,
) -> tuple[dict[str, tuple[float, float]], float, float]:
    node_ids = [node.id for node in graph.nodes]
    if not node_ids:
        return {}, MIN_CANVAS_W, MIN_CANVAS_H
    sequence = _numbered_sequence(graph)
    fans = _actor_fans(graph)
    grid = _construct_seed(graph)
    grid = _refine_forces(grid, graph)
    positions, width, height = _framed(grid)
    start = sequence[0][0] if sequence else None
    positions = _orient_start_top_left(positions, width, height, start, fans)
    return positions, width, height


def _construction_order(graph: DiagramGraph) -> list[tuple[str, str, bool]]:
    """Distinct non-self edges as (source, target, numbered), ordered so
    activities appear in ascending sequence number (path order within an
    activity, first appearance breaking ties). Walking this order lets the
    seed grow the diagram in reading order 1 -> 2 -> 3."""
    activity_number: dict[object, int] = {}
    for edge in graph.edges:
        if edge.number is not None:
            activity_number.setdefault(edge.activity_id, edge.number)

    ordered: list[tuple[float, int, str, str, bool]] = []
    seen: set[tuple[str, str]] = set()
    for appearance, edge in enumerate(graph.edges):
        if edge.source == edge.target:
            continue
        key = (edge.source, edge.target)
        if key in seen:
            continue
        seen.add(key)
        rank = activity_number.get(edge.activity_id, math.inf)
        ordered.append(
            (rank, appearance, edge.source, edge.target, edge.number is not None)
        )
    ordered.sort(key=lambda item: (item[0], item[1]))
    return [
        (source, target, numbered) for _rank, _app, source, target, numbered in ordered
    ]


def _place_free_node(
    new_id: str,
    positions: dict[str, tuple[float, float]],
    drawn: list[tuple[str, str]],
) -> tuple[float, float]:
    """Seat a node that has no placed neighbour yet. The very first node lands
    at the origin; a later rootless node spirals outward from the centroid
    until it clears every node and drawn edge. A clear seat always exists once
    the radius exceeds every placed node, so the trailing assert is an
    invariant guard (mirrors `_slide_label`), never a reachable fallback.

    The baseline is the *current* crossing/graze count of `drawn`, not always
    zero: an edge between two nodes that were both already placed (e.g. an
    actor-to-actor handoff) is appended without a placement step of its own,
    and can leave an unavoidable graze the earlier nodes could not have
    foreseen. Requiring literal zero from then on would make every later
    placement impossible; requiring "no worse than the existing baseline"
    (`_move_is_valid`'s actual contract) keeps the search always solvable."""
    if not positions:
        return (0.0, 0.0)
    base_segments = [
        (positions[source], positions[target], source, target)
        for source, target in drawn
    ]
    base_crossings = _count_overlaps(base_segments)
    base_grazes = _grazes(positions, drawn)
    centre_x = sum(x for x, _ in positions.values()) / len(positions)
    centre_y = sum(y for _, y in positions.values()) / len(positions)
    radius = CONSTRUCT_RADIUS
    placement: tuple[float, float] | None = None
    for _ in range(MAX_RADIUS_STEPS):
        for step in range(CONSTRUCT_ANGLE_STEPS):
            angle = 2.0 * math.pi * step / CONSTRUCT_ANGLE_STEPS
            candidate = (
                centre_x + radius * math.cos(angle),
                centre_y + radius * math.sin(angle),
            )
            trial = {**positions, new_id: candidate}
            if _move_is_valid(
                trial, drawn, base_crossings=base_crossings, base_grazes=base_grazes
            ):
                placement = candidate
                break
        if placement is not None:
            break
        radius *= RADIUS_GROWTH
    assert placement is not None, f'no clear seat for {new_id!r}'
    return placement


def _place_new_node(
    new_id: str,
    anchor_id: str,
    prev_angle: float | None,
    positions: dict[str, tuple[float, float]],
    drawn: list[tuple[str, str]],
    other_anchor_id: str | None = None,
) -> tuple[float, float]:
    """Seat new_id around its placed anchor. Candidates are swept by angle at a
    preferred radius that grows until at least one is crossing-free (there is
    always a free direction in open space, so this terminates -- the trailing
    assert is an invariant guard, not a reachable fallback). Among the
    crossing-free candidates at the first successful radius, prefer the smallest
    clockwise turn from the anchor's previous numbered spoke (prev_angle), else
    the default reading direction; break ties by angle index for determinism.
    Screen coords are y-down, so an increasing angle sweeps clockwise.

    The baseline passed to `_move_is_valid` is the *current* crossing/graze
    count of `drawn` (before this edge), not always zero -- see
    `_place_free_node` for why an unavoidable baseline graze can already
    exist by the time a later node is placed.

    `other_anchor_id`, when given, is a second already-placed node that
    new_id will also connect to later in the walk (a path's middle node with
    both a predecessor and a successor, e.g. "sends -> Confirmation -> to").
    Without accounting for it here, that second edge would land as a
    "closing" edge between two fixed nodes with no placement freedom left --
    the design spec's non-planar guard -- even on a genuinely planar story.
    Folding the second edge into this search keeps both crossing-free at
    once, so the later closing edge is safe by construction."""
    anchor_x, anchor_y = positions[anchor_id]
    base_segments = [
        (positions[source], positions[target], source, target)
        for source, target in drawn
    ]
    base_crossings = _count_overlaps(base_segments)
    base_grazes = _grazes(positions, drawn)
    edges_with_new = [*drawn, (anchor_id, new_id)]
    if other_anchor_id is not None:
        edges_with_new = [*edges_with_new, (new_id, other_anchor_id)]
    reference = DEFAULT_DIRECTION if prev_angle is None else prev_angle
    radius = CONSTRUCT_RADIUS
    best: tuple[float, float] | None = None
    for _ in range(MAX_RADIUS_STEPS):
        best_key: tuple[float, float] | None = None
        for step in range(CONSTRUCT_ANGLE_STEPS):
            angle = 2.0 * math.pi * step / CONSTRUCT_ANGLE_STEPS
            candidate = (
                anchor_x + radius * math.cos(angle),
                anchor_y + radius * math.sin(angle),
            )
            trial = {**positions, new_id: candidate}
            if not _move_is_valid(
                trial,
                edges_with_new,
                base_crossings=base_crossings,
                base_grazes=base_grazes,
            ):
                continue
            clockwise_turn = (angle - reference) % (2.0 * math.pi)
            key = (clockwise_turn, float(step))
            if best_key is None or key < best_key:
                best, best_key = candidate, key
        if best is not None:
            break
        radius *= RADIUS_GROWTH
    assert best is not None, f'no crossing-free placement for {new_id!r}'
    return best


def _construct_seed(graph: DiagramGraph) -> dict[str, tuple[float, float]]:
    """Phase 1: place nodes by adding activities in numbered order. Each new
    node is seated only at a crossing-free position; every node therefore
    starts at zero crossings. Actor fans are grown clockwise by tracking the
    angle of each actor's last placed numbered spoke."""
    order = _construction_order(graph)
    positions: dict[str, tuple[float, float]] = {}
    drawn: list[tuple[str, str]] = []
    last_spoke_angle: dict[str, float] = {}
    forced = False

    def angle_from(anchor_id: str, node_id: str) -> float:
        anchor_x, anchor_y = positions[anchor_id]
        node_x, node_y = positions[node_id]
        return math.atan2(node_y - anchor_y, node_x - anchor_x)

    def closing_partner(node_id: str, after_index: int, exclude_id: str) -> str | None:
        """If node_id (about to be placed) reconnects later in the walk to a
        node that is already placed, return that node -- so _place_new_node
        can satisfy both edges at once instead of leaving the later one a
        closing edge with no placement freedom (see _place_new_node)."""
        for later_source, later_target, _numbered in order[after_index + 1 :]:
            if (
                later_source == node_id
                and later_target != exclude_id
                and later_target in positions
            ):
                return later_target
            if (
                later_target == node_id
                and later_source != exclude_id
                and later_source in positions
            ):
                return later_source
        return None

    for index, (source, target, numbered) in enumerate(order):
        both_placed = source in positions and target in positions
        if source not in positions and target not in positions:
            positions[source] = _place_free_node(source, positions, drawn)
        if source not in positions:
            prev = last_spoke_angle.get(target) if numbered else None
            other = closing_partner(source, index, target)
            positions[source] = _place_new_node(
                source, target, prev, positions, drawn, other
            )
        if target not in positions:
            prev = last_spoke_angle.get(source) if numbered else None
            other = closing_partner(target, index, source)
            positions[target] = _place_new_node(
                target, source, prev, positions, drawn, other
            )
        drawn.append((source, target))
        if both_placed and not forced:
            # Both endpoints were already fixed by earlier steps, so this
            # closing edge had no placement freedom left. On a genuinely
            # non-planar story (e.g. K5) that can force a crossing no
            # placement could have avoided -- surface it once rather than
            # silently drawing over it.
            segments = [(positions[a], positions[b], a, b) for a, b in drawn]
            if _count_overlaps(segments) > 0:
                warnings.warn(
                    f'non-planar story {graph.title!r}: a step connecting two '
                    f'already-placed nodes forced an edge crossing',
                    stacklevel=2,
                )
                forced = True
        if numbered:
            last_spoke_angle[source] = angle_from(source, target)

    # Any node with no non-self edge (isolated) never entered the walk.
    for node in graph.nodes:
        if node.id not in positions:
            positions[node.id] = _place_free_node(node.id, positions, drawn)
    return positions


def _directed_edges(graph: DiagramGraph) -> list[tuple[str, str]]:
    """Distinct non-self (source, target) pairs in first-appearance order:
    parallel duplicates (a multi-path activity's shared first step) collapse
    to one, and self-loops are dropped -- the same edge set every crossing
    and graze check in this module is defined over."""
    seen: set[tuple[str, str]] = set()
    directed: list[tuple[str, str]] = []
    for edge in graph.edges:
        pair = (edge.source, edge.target)
        if edge.source == edge.target or pair in seen:
            continue
        seen.add(pair)
        directed.append(pair)
    return directed


def _net_force(
    node_id: str,
    positions: dict[str, tuple[float, float]],
    adjacency: dict[str, list[str]],
    seq_partners: dict[str, list[str]],
) -> tuple[float, float]:
    """Force on node_id: edge springs toward EDGE_REST_LENGTH, a
    preferred-distance pair potential against every other node (repel below
    PREFERRED_DIST, gently attract out to INFLUENCE_RADIUS), and a weak sequence
    spring toward the targets of adjacent-numbered activities."""
    node_x, node_y = positions[node_id]
    force_x = force_y = 0.0

    for other_id, (other_x, other_y) in positions.items():
        if other_id == node_id:
            continue
        dx, dy = node_x - other_x, node_y - other_y
        dist = math.hypot(dx, dy) or 1e-6
        unit_x, unit_y = dx / dist, dy / dist
        if dist < PREFERRED_DIST:
            magnitude = REPULSION_K * (PREFERRED_DIST - dist)
        elif dist < INFLUENCE_RADIUS:
            magnitude = -ATTRACT_K * (dist - PREFERRED_DIST)
        else:
            magnitude = 0.0
        force_x += unit_x * magnitude
        force_y += unit_y * magnitude

    for neighbour_id in adjacency[node_id]:
        other_x, other_y = positions[neighbour_id]
        dx, dy = other_x - node_x, other_y - node_y
        dist = math.hypot(dx, dy) or 1e-6
        pull = SPRING_K * (dist - EDGE_REST_LENGTH)
        force_x += (dx / dist) * pull
        force_y += (dy / dist) * pull

    for partner_id in seq_partners[node_id]:
        other_x, other_y = positions[partner_id]
        dx, dy = other_x - node_x, other_y - node_y
        dist = math.hypot(dx, dy) or 1e-6
        force_x += (dx / dist) * SEQUENCE_K * dist
        force_y += (dy / dist) * SEQUENCE_K * dist

    return force_x, force_y


def _refine_forces(
    seed: dict[str, tuple[float, float]],
    graph: DiagramGraph,
) -> dict[str, tuple[float, float]]:
    """Phase 2: deterministic Gauss-Seidel relaxation. Nodes are visited in a
    fixed (sorted) order; each proposed displacement is capped at MAX_STEP and
    accepted only if the whole layout stays crossing-free, overlap-free and
    graze-free (an unsafe step is binary-searched back to the largest safe
    fraction). Cooling shrinks the cap linearly to zero."""
    positions = dict(seed)
    directed = _directed_edges(graph)
    ordered = sorted(positions)

    adjacency: dict[str, list[str]] = {node_id: [] for node_id in positions}
    for source, target in directed:
        adjacency[source].append(target)
        adjacency[target].append(source)

    sequence = _numbered_sequence(graph)
    seq_partners: dict[str, list[str]] = {node_id: [] for node_id in positions}
    targets = [target for _source, target in sequence]
    for earlier, later in itertools.pairwise(targets):
        if earlier != later:
            seq_partners[earlier].append(later)
            seq_partners[later].append(earlier)

    base_crossings = _count_overlaps(
        [(positions[s], positions[t], s, t) for s, t in directed]
    )
    base_grazes = _grazes(positions, directed)

    for iteration in range(FORCE_ITERATIONS):
        cap = MAX_STEP * (1.0 - iteration / FORCE_ITERATIONS)
        moved = False
        for node_id in ordered:
            force_x, force_y = _net_force(node_id, positions, adjacency, seq_partners)
            magnitude = math.hypot(force_x, force_y)
            if magnitude < 1e-9:
                continue
            scale = min(cap, magnitude) / magnitude
            origin = positions[node_id]
            move_target = (origin[0] + force_x * scale, origin[1] + force_y * scale)
            fraction = 1.0
            for _ in range(6):  # binary search back to the largest safe step
                candidate = (
                    origin[0] + (move_target[0] - origin[0]) * fraction,
                    origin[1] + (move_target[1] - origin[1]) * fraction,
                )
                positions[node_id] = candidate
                if _move_is_valid(positions, directed, base_crossings, base_grazes):
                    moved = True
                    break
                positions[node_id] = origin
                fraction *= 0.5
        if not moved:
            break
    return positions


def _reflect(
    positions: dict[str, tuple[float, float]],
    width: float,
    height: float,
    flip: tuple[bool, bool],
) -> dict[str, tuple[float, float]]:
    flip_x, flip_y = flip
    return {
        node_id: (width - x if flip_x else x, height - y if flip_y else y)
        for node_id, (x, y) in positions.items()
    }


def _orient_start_top_left(
    positions: dict[str, tuple[float, float]],
    width: float,
    height: float,
    start: str | None,
    fans: list[tuple[str, tuple[str, ...]]],
) -> dict[str, tuple[float, float]]:
    """Third priority: the story should read from the top-left. Reflecting the
    whole diagram horizontally and/or vertically is an isometry -- it preserves
    every edge crossing and every distance between numbered steps -- so among
    the four axis-aligned reflections we keep the one that lands the story's
    start node (activity 1's initiator) nearest the top-left corner.

    A reflection is also the *only* transform here that flips handedness: a
    single-axis flip turns a clockwise fan counter-clockwise. So the reflection
    is chosen clockwise-aware -- start-corner distance decides first (third
    priority), and the post-reflection clockwise disorder breaks any tie
    (fourth priority) -- to keep a handedness-reversing flip from silently
    undoing the clockwise arrangement the local search found. This never costs
    a crossing or loosens the sequence grouping."""
    if start is None or start not in positions:
        return positions
    start_x, start_y = positions[start]
    flips = [(False, False), (True, False), (False, True), (True, True)]

    def corner_distance(flip: tuple[bool, bool]) -> float:
        flip_x, flip_y = flip
        return (width - start_x if flip_x else start_x) + (
            height - start_y if flip_y else start_y
        )

    def disorder(flip: tuple[bool, bool]) -> float:
        return _clockwise_disorder(fans, _reflect(positions, width, height, flip))

    flip = min(
        flips,
        key=lambda flip: (corner_distance(flip), disorder(flip), flips.index(flip)),
    )
    if flip == (False, False):
        return positions
    return _reflect(positions, width, height, flip)


def _numbered_sequence(graph: DiagramGraph) -> list[tuple[str, str]]:
    """The (source, target) of each activity's first edge, ordered by the
    sequence badge. One representative per number -- a multi-path activity
    repeats its number, but a single anchor point is enough to chain the
    reading order 1 -> 2 -> 3 across the diagram."""
    seen: set[int] = set()
    numbered: list[tuple[int, str, str]] = []
    for edge in graph.edges:
        if edge.number is None or edge.number in seen:
            continue
        seen.add(edge.number)
        numbered.append((edge.number, edge.source, edge.target))
    numbered.sort(key=lambda item: item[0])
    return [(source, target) for _number, source, target in numbered]


def _actor_fans(graph: DiagramGraph) -> list[tuple[str, tuple[str, ...]]]:
    """Group the numbered activities by their initiating actor (the source of
    each number's first edge) into fans of target ids in ascending number
    order. Only actors owning >= 2 numbers form a fan. One representative
    target per number (a multi-path activity repeats its number); actors are
    ordered by their lowest number so the result is deterministic. Like
    _numbered_sequence, sort explicitly by number rather than trusting edge
    order -- activities with explicit out-of-order ids are a valid input."""
    seen: set[int] = set()
    numbered: list[tuple[int, str, str]] = []
    for edge in graph.edges:
        if edge.number is None or edge.number in seen:
            continue
        seen.add(edge.number)
        numbered.append((edge.number, edge.source, edge.target))
    numbered.sort(key=lambda item: item[0])
    order: list[str] = []
    targets_by_actor: dict[str, list[str]] = {}
    for _number, source, target in numbered:
        if source not in targets_by_actor:
            targets_by_actor[source] = []
            order.append(source)
        targets_by_actor[source].append(target)
    return [
        (actor, tuple(targets_by_actor[actor]))
        for actor in order
        if len(targets_by_actor[actor]) >= 2
    ]


def _sequence_spread(
    sequence: list[tuple[str, str]], position: dict[str, tuple[float, float]]
) -> float:
    """Total gap, in PREFERRED_DIST-widths, between the midpoints of
    consecutively numbered activity edges. Minimizing it lines the numbered
    steps up in reading order."""
    midpoints = [
        (
            (position[source][0] + position[target][0]) / 2,
            (position[source][1] + position[target][1]) / 2,
        )
        for source, target in sequence
    ]
    return sum(
        math.hypot(later[0] - earlier[0], later[1] - earlier[1]) / PREFERRED_DIST
        for earlier, later in itertools.pairwise(midpoints)
    )


def _clockwise_disorder(
    fans: list[tuple[str, tuple[str, ...]]],
    position: dict[str, tuple[float, float]],
) -> float:
    """Fourth objective: within each actor's fan of numbered spokes, the
    directions (actor -> target) should sweep clockwise as the number rises.
    Screen coordinates are y-down, so the 2D cross product of consecutive
    spokes is positive for a clockwise turn. Each adjacent pair costs 0 when
    it turns clockwise, 0.5 when the spokes are collinear, and 1.0 when it
    turns counter-clockwise. Only the relative order matters -- the absolute
    orientation is fixed later by the top-left reflection."""
    disorder = 0.0
    for actor, targets in fans:
        origin = position[actor]
        spokes = [
            (position[target][0] - origin[0], position[target][1] - origin[1])
            for target in targets
        ]
        for (ax, ay), (bx, by) in itertools.pairwise(spokes):
            cross = ax * by - ay * bx
            if cross > 1e-9:
                disorder += 0.0
            elif cross < -1e-9:
                disorder += 1.0
            else:
                disorder += 0.5
    return disorder


def _count_overlaps(
    segments: list[tuple[tuple[float, float], tuple[float, float], str, str]],
) -> int:
    """Count visually overlapping edge pairs: proper crossings and collinear
    overlaps between edges that share no node, plus near-parallel fans out of a
    shared node (two arrows drawn on top of each other)."""
    overlaps = 0
    cos_limit = math.cos(math.radians(COLLINEAR_DEG))
    for first in range(len(segments)):
        start_a, end_a, source_a, target_a = segments[first]
        for second in range(first + 1, len(segments)):
            start_b, end_b, source_b, target_b = segments[second]
            shared = {source_a, target_a} & {source_b, target_b}
            if shared:
                if len({source_a, target_a} | {source_b, target_b}) == 2:
                    # Same pair of nodes: a duplicate edge (e.g. one activity's
                    # multi-path first step) drawn on the identical line. No
                    # placement can separate two edges between the same two
                    # nodes, so this is not a resolvable crossing.
                    continue
                pivot = next(iter(shared))
                if _fan_overlaps(
                    pivot, start_a, end_a, source_a, start_b, end_b, source_b, cos_limit
                ):
                    overlaps += 1
                continue
            if _segments_cross(start_a, end_a, start_b, end_b):
                overlaps += 1
    return overlaps


def _fan_overlaps(
    pivot: str,
    start_a: tuple[float, float],
    end_a: tuple[float, float],
    source_a: str,
    start_b: tuple[float, float],
    end_b: tuple[float, float],
    source_b: str,
    cos_limit: float,
) -> bool:
    tail_a, head_a = (start_a, end_a) if source_a == pivot else (end_a, start_a)
    tail_b, head_b = (start_b, end_b) if source_b == pivot else (end_b, start_b)
    ax, ay = head_a[0] - tail_a[0], head_a[1] - tail_a[1]
    bx, by = head_b[0] - tail_b[0], head_b[1] - tail_b[1]
    length_a = math.hypot(ax, ay) or 1.0
    length_b = math.hypot(bx, by) or 1.0
    cosine = (ax * bx + ay * by) / (length_a * length_b)
    return cosine >= cos_limit


def _segments_cross(
    start_a: tuple[float, float],
    end_a: tuple[float, float],
    start_b: tuple[float, float],
    end_b: tuple[float, float],
) -> bool:
    def orientation(
        p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]
    ) -> float:
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])

    d1 = orientation(start_b, end_b, start_a)
    d2 = orientation(start_b, end_b, end_a)
    d3 = orientation(start_a, end_a, start_b)
    d4 = orientation(start_a, end_a, end_b)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    # Collinear overlap: any endpoint of one lying on the other's span.
    for point, seg_start, seg_end in (
        (start_a, start_b, end_b),
        (end_a, start_b, end_b),
        (start_b, start_a, end_a),
        (end_b, start_a, end_a),
    ):
        if abs(orientation(seg_start, seg_end, point)) < 1e-6 and _point_near_segment(
            point, seg_start, seg_end, 1e-6
        ):
            return True
    return False


def _point_near_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
    clearance: float,
) -> bool:
    seg_x, seg_y = end[0] - start[0], end[1] - start[1]
    length_sq = seg_x * seg_x + seg_y * seg_y
    if length_sq == 0.0:
        return math.hypot(point[0] - start[0], point[1] - start[1]) <= clearance
    t = ((point[0] - start[0]) * seg_x + (point[1] - start[1]) * seg_y) / length_sq
    if t <= 0.0 or t >= 1.0:  # nearest point is an endpoint (a shared node) -> fine
        return False
    proj_x, proj_y = start[0] + t * seg_x, start[1] + t * seg_y
    return math.hypot(point[0] - proj_x, point[1] - proj_y) <= clearance


def _grazes(
    positions: dict[str, tuple[float, float]],
    directed: list[tuple[str, str]],
) -> int:
    """(edge, foreign-node) pairs where the node sits within
    NODE_ON_EDGE_CLEARANCE of the edge -- an arrow running over an unrelated
    node, which the hard invariant forbids."""
    count = 0
    for source, target in directed:
        start, end = positions[source], positions[target]
        for node_id, point in positions.items():
            if node_id in (source, target):
                continue
            if _point_near_segment(point, start, end, NODE_ON_EDGE_CLEARANCE):
                count += 1
    return count


def _min_pair_distance(positions: dict[str, tuple[float, float]]) -> float:
    coords = list(positions.values())
    smallest = math.inf
    for index, (first_x, first_y) in enumerate(coords):
        for second_x, second_y in coords[index + 1 :]:
            smallest = min(smallest, math.hypot(second_x - first_x, second_y - first_y))
    return smallest


def _move_is_valid(
    positions: dict[str, tuple[float, float]],
    directed: list[tuple[str, str]],
    base_crossings: int,
    base_grazes: int,
) -> bool:
    """The hard-invariant gate: a candidate arrangement is accepted only when it
    keeps edge crossings and node grazes no worse than the baseline and no two
    nodes are closer than MIN_NODE_DIST."""
    segments = [
        (positions[source], positions[target], source, target)
        for source, target in directed
    ]
    if _count_overlaps(segments) > base_crossings:
        return False
    if _grazes(positions, directed) > base_grazes:
        return False
    return _min_pair_distance(positions) >= MIN_NODE_DIST - 1e-6


def _segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Euclidean distance from a point to a line segment (clamped to the ends)."""
    seg_x, seg_y = end[0] - start[0], end[1] - start[1]
    length_sq = seg_x * seg_x + seg_y * seg_y
    if length_sq == 0.0:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    t = ((point[0] - start[0]) * seg_x + (point[1] - start[1]) * seg_y) / length_sq
    t = max(0.0, min(1.0, t))
    proj_x, proj_y = start[0] + t * seg_x, start[1] + t * seg_y
    return math.hypot(point[0] - proj_x, point[1] - proj_y)


def _framed(
    grid: dict[str, tuple[float, float]],
) -> tuple[dict[str, tuple[float, float]], float, float]:
    """Shift the grid so its top-left node sits at (PAD, PAD) and size the
    canvas to enclose every node with PAD to spare, growing to the minimum
    canvas and re-centring smaller diagrams within it."""
    xs = [x for x, _ in grid.values()]
    ys = [y for _, y in grid.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    positions = {
        node_id: (x - min_x + PAD, y - min_y + PAD) for node_id, (x, y) in grid.items()
    }
    width = max(max_x - min_x + 2 * PAD, MIN_CANVAS_W)
    height = max(max_y - min_y + 2 * PAD, MIN_CANVAS_H)
    used_w = max_x - min_x + 2 * PAD
    used_h = max_y - min_y + 2 * PAD
    shift_x = (width - used_w) / 2
    shift_y = (height - used_h) / 2
    if shift_x or shift_y:
        positions = {
            node_id: (x + shift_x, y + shift_y) for node_id, (x, y) in positions.items()
        }
    return positions, width, height


def layout_graph(graph: DiagramGraph) -> DiagramLayout:
    positions, width, height = position_nodes(graph)
    placed_nodes = tuple(
        PlacedNode(node=node, x=positions[node.id][0], y=positions[node.id][1])
        for node in graph.nodes
    )
    node_boxes_by_id = {
        p.node.id: LabelBox(
            x=p.x - NODE_HALF_W,
            y=p.y - NODE_HALF_H,
            width=2 * NODE_HALF_W,
            height=2 * NODE_HALF_H,
        )
        for p in placed_nodes
    }
    # One node-centre line per distinct connected pair, so a label can prefer a
    # spot distinctly nearer its own arrow than any other (association clarity).
    segment_by_pair: dict[
        frozenset[str], tuple[tuple[float, float], tuple[float, float]]
    ] = {}
    for edge in graph.edges:
        if edge.source == edge.target:
            continue
        pair = frozenset((edge.source, edge.target))
        segment_by_pair.setdefault(
            pair, (positions[edge.source], positions[edge.target])
        )

    placed_edges: list[PlacedEdge] = []
    drawn: set[tuple[str, str, str, int | None]] = set()
    for edge in graph.edges:
        # One activity with several paths repeats its shared first step as
        # identical edges (e.g. "sends" toward the same object for each
        # recipient). Those draw on the exact same line, so only place the
        # first; the diverging connectives ("to Alice", "to Bob") still differ.
        signature = (edge.source, edge.target, edge.label, edge.number)
        if edge.source != edge.target and signature in drawn:
            continue
        drawn.add(signature)
        source_x, source_y = positions[edge.source]
        target_x, target_y = positions[edge.target]
        if edge.source == edge.target:
            label = _label_box(edge, source_x, source_y - NODE_HALF_H - LABEL_H - 8.0)
            placed_edges.append(
                PlacedEdge(
                    edge=edge,
                    x1=source_x,
                    y1=source_y,
                    x2=target_x,
                    y2=target_y,
                    loop=True,
                    label=label,
                )
            )
            continue
        # Obstacles: all node boxes (including this edge's own source/target
        # -- a label sliding along a short edge can still collide with the
        # boxes it connects) and previously placed labels.
        obstacles = list(node_boxes_by_id.values())
        obstacles.extend(e.label for e in placed_edges)

        dx, dy = target_x - source_x, target_y - source_y
        dist = math.hypot(dx, dy)
        # Distinct connected nodes should never coincide once the grid has been
        # placed; a zero distance here means two placed nodes with an edge
        # between them landed on the same point, which is a layout bug.
        assert dist > 0.0, f'coincident nodes {edge.source!r} and {edge.target!r}'
        ux, uy = dx / dist, dy / dist
        # Ensure trimmed edge is at least 40.0: scale down trims if needed
        # Use 40.1 to account for floating-point precision
        total_desired_trim = TRIM_SOURCE + TRIM_TARGET
        total_available_trim = max(0.0, dist - 40.1)
        scale = max(0.0, min(1.0, total_available_trim / total_desired_trim))
        trim_source = TRIM_SOURCE * scale
        trim_target = TRIM_TARGET * scale
        x1, y1 = source_x + ux * trim_source, source_y + uy * trim_source
        x2, y2 = target_x - ux * trim_target, target_y - uy * trim_target
        own_pair = frozenset((edge.source, edge.target))
        foreign_segments = tuple(
            segment for pair, segment in segment_by_pair.items() if pair != own_pair
        )
        label = _slide_label(
            edge, x1, y1, x2, y2, ux, uy, obstacles, foreign_segments
        )
        placed_edges.append(
            PlacedEdge(edge=edge, x1=x1, y1=y1, x2=x2, y2=y2, loop=False, label=label)
        )
    return DiagramLayout(
        graph=graph,
        nodes=placed_nodes,
        edges=tuple(placed_edges),
        width=width,
        height=height,
    )


def count_crossings(edges: tuple[PlacedEdge, ...]) -> int:
    """Number of overlapping drawn-edge pairs (self-loops excluded). The layout
    is built to drive this to zero; tests assert on it."""
    segments = [
        (
            (placed.x1, placed.y1),
            (placed.x2, placed.y2),
            placed.edge.source,
            placed.edge.target,
        )
        for placed in edges
        if not placed.loop
    ]
    return _count_overlaps(segments)


def _label_size(edge: DiagramEdge) -> tuple[float, float]:
    width = len(edge.label) * LABEL_CHAR_W + 8.0
    if edge.number is not None:
        width += BADGE_W
    return width, LABEL_H


def _label_box(edge: DiagramEdge, centre_x: float, centre_y: float) -> LabelBox:
    width, height = _label_size(edge)
    return LabelBox(
        x=centre_x - width / 2, y=centre_y - height / 2, width=width, height=height
    )


def _slide_label(
    edge: DiagramEdge,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    ux: float,
    uy: float,
    obstacles: list[LabelBox],
    foreign_segments: tuple[tuple[tuple[float, float], tuple[float, float]], ...] = (),
) -> LabelBox:
    """Place the label near the edge midpoint, offset perpendicular; slide it
    along the edge (alternating around the midpoint) and try both sides and a
    larger offset until it clears all obstacle boxes -- still within
    LABEL_OFFSET + LABEL_H, the "stays near its edge" bound other code relies
    on. A short edge between two crowded nodes can leave every in-line slide
    position clipping one of its own endpoints' boxes (the perpendicular
    offset is much smaller than a node's radius), hence the extra offset/side
    attempts.

    Candidates are scored by (obstacle overlap, association ambiguity, how far
    the label slid from the midpoint). Overlap dominates -- a label never
    overlaps a node or another label to look tidier. Among clear positions it
    then prefers one that sits distinctly nearer its own arrow than any other
    (foreign_segments), so which step a number+verb names is unambiguous even
    where spokes fan close together, and finally one near the edge midpoint."""
    own_start, own_end = (x1, y1), (x2, y2)
    best: LabelBox | None = None
    best_key: tuple[float, float, float] | None = None
    for side in (1.0, -1.0):
        for offset in (LABEL_OFFSET, LABEL_OFFSET + LABEL_H - 1.0):
            for attempt in range(13):
                step = (attempt + 1) // 2 * 0.08
                fraction = 0.5 + (step if attempt % 2 == 1 else -step)
                centre_x = x1 + (x2 - x1) * fraction - uy * offset * side
                centre_y = y1 + (y2 - y1) * fraction + ux * offset * side
                candidate = _label_box(edge, centre_x, centre_y)
                overlap = sum(_overlap_area(candidate, box) for box in obstacles)
                centre = (centre_x, centre_y)
                own_distance = _segment_distance(centre, own_start, own_end)
                foreign_distance = min(
                    (_segment_distance(centre, start, end)
                     for start, end in foreign_segments),
                    default=math.inf,
                )
                ambiguity = max(
                    0.0, LABEL_ASSOC_MARGIN - (foreign_distance - own_distance)
                )
                slid = abs(fraction - 0.5) + (offset - LABEL_OFFSET) * 0.001
                key = (overlap, ambiguity, slid)
                if best_key is None or key < best_key:
                    best, best_key = candidate, key
                if overlap == 0.0 and ambiguity == 0.0:
                    return candidate
    assert best is not None
    return best


def _overlap_area(box_a: LabelBox, box_b: LabelBox) -> float:
    overlap_w = min(box_a.x + box_a.width, box_b.x + box_b.width) - max(
        box_a.x, box_b.x
    )
    overlap_h = min(box_a.y + box_a.height, box_b.y + box_b.height) - max(
        box_a.y, box_b.y
    )
    return max(overlap_w, 0.0) * max(overlap_h, 0.0)
