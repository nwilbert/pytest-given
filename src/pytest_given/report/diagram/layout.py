"""Deterministic crossing-minimizing layout. Pure Python, no RNG.

The overriding rule is that drawn arrows must not overlap: no edge may cross
another edge, and (best effort) no edge may run over an unrelated node. Nodes
live at continuous (x, y) coordinates, never closer than MIN_NODE_DIST apart.
The seed is built by walking activities in ascending sequence-number order
(`_construction_order`) and seating each newly introduced node only at a
crossing-free position near its already-placed neighbour (`_construct_seed`,
`_candidate_positions`, `_place_free_node`) -- a tree is planar, so this alone
reaches zero crossings on tree-shaped stories, and each actor's numbered
spokes are swept clockwise as they are added. A node that will later close
back onto an already-placed node (both its edges known at construction time,
e.g. a path's middle step) is seated with that future edge in mind too, so a
"closing" edge between two already-fixed nodes -- which would otherwise have
no placement freedom left -- stays crossing-free on real, planar stories.
Placement is a bounded, deterministic depth-first search: each node offers its
crossing-free seats best-first (`_candidate_positions`), and when a later fan
is over-constrained (no seat reaches all its already-placed partners) the DFS
backtracks and re-seats the earlier nodes that boxed it in. Taking the first
candidate at every step reproduces the plain greedy walk, so tree-shaped and
uncrowded stories are unchanged; only over-constrained fans are re-seated. A
genuinely non-planar story exhausts the search budget and falls back to the
greedy walk (`_construct_seed_greedy`), whose closing-edge guard surfaces the
unavoidable crossing rather than hanging. Finally the whole diagram is
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
MAX_SEED_CANDIDATES = 8  # best-first seats kept per node for the backtracking DFS
MAX_SEED_PLACEMENTS = 8000  # total DFS placements before the greedy fallback

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


def _candidate_positions(
    new_id: str,
    anchor_id: str,
    prev_angle: float | None,
    positions: dict[str, tuple[float, float]],
    drawn: list[tuple[str, str]],
    other_anchor_ids: tuple[str, ...] = (),
) -> list[tuple[float, float]]:
    """The crossing-free seats for new_id around its placed anchor that satisfy
    the (anchor, new) edge AND *every* (new, other) closing edge at once.
    Candidates are swept by angle at a preferred radius that grows until at
    least one is valid; all valid seats at that first successful radius are
    returned, ordered best-first by (clockwise turn from prev_angle, else the
    default reading direction; then angle index for determinism) and capped at
    MAX_SEED_CANDIDATES. Screen coords are y-down, so an increasing angle sweeps
    clockwise, and candidates[0] is exactly the single seat the plain greedy
    walk would have taken.

    `other_anchor_ids` are every *already-placed* node that new_id will also
    connect to later in the walk (a path's middle node with both a predecessor
    and a successor, e.g. "sends -> Confirmation -> to", or a multi-path
    activity whose object fans out to several already-seated recipients --
    "sends Confirmation to Alice *and* Bob"). Folding them all into this search
    keeps every closing edge crossing-free at once, so the later closing edges
    are safe by construction. With `other_anchor_ids=()` this is the plain
    single-anchor placement.

    There is **no relaxation** here: a point that satisfies every closing edge
    at once need not exist even when the graph is planar (earlier placements can
    box the anchors in), and dropping a closing edge is exactly what draws a
    crossing. An empty list means "new_id cannot be seated given the current
    earlier placements" -- the caller (`_construct_seed`'s DFS) backtracks and
    re-seats the nodes that boxed it in rather than accepting a crossing.

    A candidate is accepted by `_candidate_is_valid`, an incremental form of
    `_move_is_valid`: since only new_id moves, the drawn edges' mutual crossings
    and the placed nodes' spacing are unchanged, so it suffices to check new_id
    and its new edges against everything already placed. This is exactly
    equivalent to re-running `_move_is_valid` over the whole layout (the earlier
    layout already satisfies the invariants), but avoids the full O(edges^2)
    re-count per candidate -- the difference between a snappy backtracking search
    and one that stalls on crowded fans."""
    anchor_x, anchor_y = positions[anchor_id]
    reference = DEFAULT_DIRECTION if prev_angle is None else prev_angle
    new_pairs = [
        (anchor_id, new_id),
        *((new_id, other) for other in other_anchor_ids),
    ]
    drawn_segments = [(positions[s], positions[t], s, t) for s, t in drawn]
    cos_limit = math.cos(math.radians(COLLINEAR_DEG))
    radius = CONSTRUCT_RADIUS
    for _ in range(MAX_RADIUS_STEPS):
        scored: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for step in range(CONSTRUCT_ANGLE_STEPS):
            angle = 2.0 * math.pi * step / CONSTRUCT_ANGLE_STEPS
            candidate = (
                anchor_x + radius * math.cos(angle),
                anchor_y + radius * math.sin(angle),
            )
            if _candidate_is_valid(
                new_id,
                candidate,
                new_pairs,
                drawn,
                drawn_segments,
                positions,
                cos_limit,
            ):
                clockwise_turn = (angle - reference) % (2.0 * math.pi)
                scored.append(((clockwise_turn, float(step)), candidate))
        if scored:
            scored.sort(key=lambda item: item[0])
            return [candidate for _key, candidate in scored[:MAX_SEED_CANDIDATES]]
        radius *= RADIUS_GROWTH
    return []


def _candidate_is_valid(
    new_id: str,
    candidate: tuple[float, float],
    new_pairs: list[tuple[str, str]],
    drawn: list[tuple[str, str]],
    drawn_segments: list[tuple[tuple[float, float], tuple[float, float], str, str]],
    positions: dict[str, tuple[float, float]],
    cos_limit: float,
) -> bool:
    """Whether seating new_id at `candidate` keeps the layout valid, checked
    incrementally (see `_candidate_positions`). `positions` holds the already
    placed nodes (without new_id); `new_pairs` are new_id's edges. Equivalent to
    `_move_is_valid({**positions, new_id: candidate}, drawn + new_pairs, base
    crossings, base grazes)` because the pre-existing layout already meets every
    invariant, so only new_id's contribution can newly violate one."""
    # No placed node closer than MIN_NODE_DIST to the new seat.
    for other_x, other_y in positions.values():
        if math.hypot(candidate[0] - other_x, candidate[1] - other_y) < (
            MIN_NODE_DIST - 1e-6
        ):
            return False
    new_segments = [
        (
            candidate if source == new_id else positions[source],
            candidate if target == new_id else positions[target],
            source,
            target,
        )
        for source, target in new_pairs
    ]
    # No new edge may overlap a drawn edge or another new edge.
    for index, new_segment in enumerate(new_segments):
        for drawn_segment in drawn_segments:
            if _segments_overlap(new_segment, drawn_segment, cos_limit):
                return False
        for other_new in new_segments[index + 1 :]:
            if _segments_overlap(new_segment, other_new, cos_limit):
                return False
    # No new graze: new_id must clear every drawn edge, and every new edge must
    # clear every foreign placed node.
    for source, target in drawn:
        if _point_near_segment(
            candidate, positions[source], positions[target], NODE_ON_EDGE_CLEARANCE
        ):
            return False
    for start, end, source, target in new_segments:
        for other_id, point in positions.items():
            if other_id in (source, target):
                continue
            if _point_near_segment(point, start, end, NODE_ON_EDGE_CLEARANCE):
                return False
    return True


def _place_new_node(
    new_id: str,
    anchor_id: str,
    prev_angle: float | None,
    positions: dict[str, tuple[float, float]],
    drawn: list[tuple[str, str]],
    other_anchor_ids: tuple[str, ...] = (),
) -> tuple[float, float]:
    """Greedy single seat for new_id: the best crossing-free candidate that
    satisfies as many closing edges as possible. Used only by the greedy
    fallback (`_construct_seed_greedy`); the backtracking seed calls
    `_candidate_positions` directly.

    A point that satisfies *every* closing edge at once need not exist even
    when the graph is planar: earlier greedy placements can box the anchors in
    so no single seat reaches them all crossing-free (e.g. a confirmation
    fanning back to two guests already seated far apart). Rather than fail, the
    closing set is relaxed one edge at a time (dropping the latest-numbered
    partner first) until a seat is found; the anchor-only case always succeeds,
    so the trailing assert stays an unreachable invariant guard. Any closing
    edge dropped here is drawn later as a plain closing edge, where the
    non-planar guard surfaces the residual crossing -- correct behaviour for a
    genuinely over-constrained greedy seed."""
    best: tuple[float, float] | None = None
    for keep in range(len(other_anchor_ids), -1, -1):
        candidates = _candidate_positions(
            new_id, anchor_id, prev_angle, positions, drawn, other_anchor_ids[:keep]
        )
        if candidates:
            best = candidates[0]
            break
    assert best is not None, f'no crossing-free placement for {new_id!r}'
    return best


@dataclass(frozen=True, kw_only=True)
class _SeedStep:
    """One decision in the construction walk the backtracking DFS drives.

    kind 'free': seat node_id with no placed neighbour yet (`_place_free_node`);
        a single, always-available candidate.
    kind 'node': seat node_id around the placed anchor_id
        (`_candidate_positions`), reading the anchor's last numbered spoke when
        `numbered`, and satisfying every `others` closing edge at once.
    kind 'close': record the edge (source, target) as drawn and, when
        `numbered`, set source's last spoke angle. When `both_placed` both
        endpoints were fixed by earlier steps, so this closing edge had no
        placement freedom: it is a checkpoint that dead-ends if it crosses."""

    kind: str
    node_id: str = ''
    anchor_id: str = ''
    numbered: bool = False
    others: tuple[str, ...] = ()
    source: str = ''
    target: str = ''
    both_placed: bool = False


@dataclass(frozen=True, kw_only=True)
class _SeedUndo:
    """How to revert one applied `_SeedStep` when the DFS backtracks."""

    placed_id: str | None  # a node to remove from positions ('free'/'node')
    popped_drawn: bool  # whether to pop the last appended drawn edge ('close')
    spoke_key: str | None  # actor whose last spoke angle was set ('close')
    spoke_prev: float  # its previous value, restored only when spoke_existed
    spoke_existed: bool


# A "close" step places nothing; this sentinel stands in for its single
# candidate so the DFS drives every decision uniformly.
_SEED_PROCEED: tuple[float, float] = (0.0, 0.0)


def _seed_steps(order: list[tuple[str, str, bool]]) -> list[_SeedStep]:
    """Flatten the construction walk into the ordered placement decisions the
    DFS drives. Which nodes are newly placed at each entry -- and therefore each
    entry's closing partners -- depends only on the walk order, not on where the
    nodes land, so the whole decision sequence is static and precomputable."""
    placed: set[str] = set()
    steps: list[_SeedStep] = []

    def closing_partners(
        node_id: str, after_index: int, exclude_id: str
    ) -> tuple[str, ...]:
        """Every already-placed node that node_id reconnects to later in the
        walk -- so `_candidate_positions` can satisfy all those edges at once
        instead of leaving each a closing edge with no placement freedom. A
        later edge whose other endpoint is not placed yet is not a closing
        constraint now: that endpoint gets its own freedom when its turn comes."""
        partners: list[str] = []
        for later_source, later_target, _numbered in order[after_index + 1 :]:
            if (
                later_source == node_id
                and later_target != exclude_id
                and later_target in placed
                and later_target not in partners
            ):
                partners.append(later_target)
            elif (
                later_target == node_id
                and later_source != exclude_id
                and later_source in placed
                and later_source not in partners
            ):
                partners.append(later_source)
        return tuple(partners)

    for index, (source, target, numbered) in enumerate(order):
        both_placed = source in placed and target in placed
        if source not in placed and target not in placed:
            steps.append(_SeedStep(kind='free', node_id=source))
            placed.add(source)
        if source not in placed:
            steps.append(
                _SeedStep(
                    kind='node',
                    node_id=source,
                    anchor_id=target,
                    numbered=numbered,
                    others=closing_partners(source, index, target),
                )
            )
            placed.add(source)
        if target not in placed:
            steps.append(
                _SeedStep(
                    kind='node',
                    node_id=target,
                    anchor_id=source,
                    numbered=numbered,
                    others=closing_partners(target, index, source),
                )
            )
            placed.add(target)
        steps.append(
            _SeedStep(
                kind='close',
                source=source,
                target=target,
                numbered=numbered,
                both_placed=both_placed,
            )
        )
    return steps


def _step_candidates(
    step: _SeedStep,
    positions: dict[str, tuple[float, float]],
    drawn: list[tuple[str, str]],
    last_spoke_angle: dict[str, float],
) -> list[tuple[float, float]]:
    """The candidates the DFS may try for `step` given the current state,
    best-first. A 'free' step has one seat; a 'node' step has its best-first
    crossing-free seats; a 'close' step yields the proceed sentinel unless it is
    a both-placed checkpoint whose edge would cross (then an empty list, a dead
    end that makes the DFS re-seat the nodes that boxed the edge in)."""
    if step.kind == 'free':
        return [_place_free_node(step.node_id, positions, drawn)]
    if step.kind == 'node':
        prev = last_spoke_angle.get(step.anchor_id) if step.numbered else None
        return _candidate_positions(
            step.node_id, step.anchor_id, prev, positions, drawn, step.others
        )
    if not step.both_placed:
        return [_SEED_PROCEED]
    base_segments = [(positions[a], positions[b], a, b) for a, b in drawn]
    base_crossings = _count_overlaps(base_segments)
    base_grazes = _grazes(positions, drawn)
    trial = [*drawn, (step.source, step.target)]
    if _move_is_valid(positions, trial, base_crossings, base_grazes):
        return [_SEED_PROCEED]
    return []


def _apply_step(
    step: _SeedStep,
    candidate: tuple[float, float],
    positions: dict[str, tuple[float, float]],
    drawn: list[tuple[str, str]],
    last_spoke_angle: dict[str, float],
) -> _SeedUndo:
    """Apply `step`'s chosen candidate, mutating the DFS state and returning how
    to revert it."""
    if step.kind in ('free', 'node'):
        positions[step.node_id] = candidate
        return _SeedUndo(
            placed_id=step.node_id,
            popped_drawn=False,
            spoke_key=None,
            spoke_prev=0.0,
            spoke_existed=False,
        )
    drawn.append((step.source, step.target))
    spoke_key: str | None = None
    spoke_prev = 0.0
    spoke_existed = False
    if step.numbered:
        spoke_key = step.source
        spoke_existed = step.source in last_spoke_angle
        spoke_prev = last_spoke_angle[step.source] if spoke_existed else 0.0
        anchor_x, anchor_y = positions[step.source]
        node_x, node_y = positions[step.target]
        last_spoke_angle[step.source] = math.atan2(
            node_y - anchor_y, node_x - anchor_x
        )
    return _SeedUndo(
        placed_id=None,
        popped_drawn=True,
        spoke_key=spoke_key,
        spoke_prev=spoke_prev,
        spoke_existed=spoke_existed,
    )


def _undo_step(
    undo: _SeedUndo,
    positions: dict[str, tuple[float, float]],
    drawn: list[tuple[str, str]],
    last_spoke_angle: dict[str, float],
) -> None:
    if undo.placed_id is not None:
        del positions[undo.placed_id]
    if undo.popped_drawn:
        drawn.pop()
    if undo.spoke_key is not None:
        if undo.spoke_existed:
            last_spoke_angle[undo.spoke_key] = undo.spoke_prev
        else:
            del last_spoke_angle[undo.spoke_key]


def _blame_depth(steps: list[_SeedStep], dead_depth: int) -> int:
    """Where to backtrack after a *dead end* -- a step whose candidate list came
    back empty (a node with no crossing-free seat, or a both-placed closing edge
    that crosses). The blame is the already-placed nodes that over-constrained
    it: a node step's anchor and closing partners, a closing edge's two
    endpoints. Jumping straight back to the deepest re-seatable ('node') blamer
    -- skipping the independent nodes seated in between, which cannot relieve the
    conflict -- is what keeps the search from exploding when the culprit sits far
    upstream (e.g. a confirmation fanning back to guests seated many steps
    earlier). With no re-seatable blamer, fall back to the previous decision."""
    step = steps[dead_depth]
    if step.kind == 'node':
        blamed = (step.anchor_id, *step.others)
    else:  # a both-placed closing-edge checkpoint
        blamed = (step.source, step.target)
    placer_by_node = {
        placed.node_id: earlier
        for earlier in range(dead_depth)
        if (placed := steps[earlier]).kind == 'node'
    }
    depths = [
        placer_by_node[node_id] for node_id in blamed if node_id in placer_by_node
    ]
    return max(depths) if depths else dead_depth - 1


def _construct_seed(graph: DiagramGraph) -> dict[str, tuple[float, float]]:
    """Phase 1: seat nodes by adding activities in numbered order via a bounded,
    deterministic depth-first search (see the module docstring). Each decision
    offers its crossing-free seats best-first; a dead end -- a node with no seat,
    or a both-placed closing edge that would cross -- backtracks (jumping to the
    deepest node that over-constrained it, `_blame_depth`) and advances that
    decision. Taking the first seat at every decision reproduces
    `_construct_seed_greedy`, so tree-shaped and uncrowded stories are seated
    identically; only over-constrained fans are re-seated. If the search exceeds
    MAX_SEED_PLACEMENTS attempts, or exhausts every branch (a genuinely
    non-planar story), it abandons the DFS and returns the greedy walk, whose
    guard surfaces the unavoidable crossing rather than the build hanging."""
    steps = _seed_steps(_construction_order(graph))
    positions: dict[str, tuple[float, float]] = {}
    drawn: list[tuple[str, str]] = []
    last_spoke_angle: dict[str, float] = {}

    candidates_stack: list[list[tuple[float, float]]] = []
    cursor_stack: list[int] = []
    undo_stack: list[_SeedUndo] = []

    def backtrack_to(target: int) -> int:
        # Undo and drop every applied frame above `target`, then undo target's
        # own placement and advance it to its next candidate; returns the new
        # depth (target). The frame at `target` is kept: its candidates were
        # computed from the now-restored earlier state and stay valid.
        while len(cursor_stack) - 1 > target:
            candidates_stack.pop()
            cursor_stack.pop()
            _undo_step(undo_stack.pop(), positions, drawn, last_spoke_angle)
        _undo_step(undo_stack.pop(), positions, drawn, last_spoke_angle)
        cursor_stack[target] += 1
        return target

    attempts = 0
    depth = 0
    while depth < len(steps):
        if attempts > MAX_SEED_PLACEMENTS:
            return _construct_seed_greedy(graph)
        step = steps[depth]
        if depth == len(candidates_stack):
            candidates_stack.append(
                _step_candidates(step, positions, drawn, last_spoke_angle)
            )
            cursor_stack.append(0)
        cursor = cursor_stack[depth]
        if cursor < len(candidates_stack[depth]):
            attempts += 1
            undo_stack.append(
                _apply_step(
                    step,
                    candidates_stack[depth][cursor],
                    positions,
                    drawn,
                    last_spoke_angle,
                )
            )
            depth += 1
            continue
        # No candidate left at this decision. An empty list is a dead end (this
        # step cannot be satisfied): jump back to the deepest node that
        # over-constrained it. An *exhausted* non-empty list means every seat
        # here led downstream to failure: step back chronologically.
        if not candidates_stack[depth]:
            target = _blame_depth(steps, depth)
        else:
            target = depth - 1
        candidates_stack.pop()
        cursor_stack.pop()
        if target < 0:
            return _construct_seed_greedy(graph)
        depth = backtrack_to(target)

    # Any node with no non-self edge (isolated) never entered the walk.
    for node in graph.nodes:
        if node.id not in positions:
            positions[node.id] = _place_free_node(node.id, positions, drawn)
    return positions


def _construct_seed_greedy(graph: DiagramGraph) -> dict[str, tuple[float, float]]:
    """Bounded fallback for `_construct_seed`: the plain forward greedy walk.
    Places nodes by adding activities in numbered order, each new node seated at
    the single best crossing-free position near its anchor (`_place_new_node`,
    which relaxes an over-constrained closing set rather than backtracking).
    Used when the backtracking DFS exhausts its placement budget -- on a
    genuinely non-planar story, so the closing-edge guard below still surfaces
    the unavoidable crossing rather than the build hanging."""
    order = _construction_order(graph)
    positions: dict[str, tuple[float, float]] = {}
    drawn: list[tuple[str, str]] = []
    last_spoke_angle: dict[str, float] = {}
    forced = False

    def angle_from(anchor_id: str, node_id: str) -> float:
        anchor_x, anchor_y = positions[anchor_id]
        node_x, node_y = positions[node_id]
        return math.atan2(node_y - anchor_y, node_x - anchor_x)

    def closing_partners(
        node_id: str, after_index: int, exclude_id: str
    ) -> tuple[str, ...]:
        """Every already-placed node that node_id (about to be placed)
        reconnects to later in the walk -- so _place_new_node can satisfy all
        those edges at once instead of leaving each a closing edge with no
        placement freedom (see _place_new_node). A later edge whose other
        endpoint is not placed yet is *not* a closing constraint now: that
        endpoint gets its own placement freedom when its turn comes, so it is
        excluded here."""
        partners: list[str] = []
        for later_source, later_target, _numbered in order[after_index + 1 :]:
            if (
                later_source == node_id
                and later_target != exclude_id
                and later_target in positions
                and later_target not in partners
            ):
                partners.append(later_target)
            elif (
                later_target == node_id
                and later_source != exclude_id
                and later_source in positions
                and later_source not in partners
            ):
                partners.append(later_source)
        return tuple(partners)

    for index, (source, target, numbered) in enumerate(order):
        both_placed = source in positions and target in positions
        if source not in positions and target not in positions:
            positions[source] = _place_free_node(source, positions, drawn)
        if source not in positions:
            prev = last_spoke_angle.get(target) if numbered else None
            others = closing_partners(source, index, target)
            positions[source] = _place_new_node(
                source, target, prev, positions, drawn, others
            )
        if target not in positions:
            prev = last_spoke_angle.get(source) if numbered else None
            others = closing_partners(target, index, source)
            positions[target] = _place_new_node(
                target, source, prev, positions, drawn, others
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


def _segments_overlap(
    segment_a: tuple[tuple[float, float], tuple[float, float], str, str],
    segment_b: tuple[tuple[float, float], tuple[float, float], str, str],
    cos_limit: float,
) -> bool:
    """Whether two drawn edges visually overlap: a near-parallel fan when they
    share a node, else a proper crossing or collinear overlap. Two edges between
    the *same* pair of nodes (a duplicate first step) never overlap-resolvably.
    The single source of truth for both the full `_count_overlaps` sweep and the
    incremental per-candidate check in `_candidate_positions`."""
    start_a, end_a, source_a, target_a = segment_a
    start_b, end_b, source_b, target_b = segment_b
    shared = {source_a, target_a} & {source_b, target_b}
    if shared:
        if len({source_a, target_a} | {source_b, target_b}) == 2:
            return False
        pivot = next(iter(shared))
        return _fan_overlaps(
            pivot, start_a, end_a, source_a, start_b, end_b, source_b, cos_limit
        )
    return _segments_cross(start_a, end_a, start_b, end_b)


def _count_overlaps(
    segments: list[tuple[tuple[float, float], tuple[float, float], str, str]],
) -> int:
    """Count visually overlapping edge pairs: proper crossings and collinear
    overlaps between edges that share no node, plus near-parallel fans out of a
    shared node (two arrows drawn on top of each other)."""
    overlaps = 0
    cos_limit = math.cos(math.radians(COLLINEAR_DEG))
    for first in range(len(segments)):
        for second in range(first + 1, len(segments)):
            if _segments_overlap(segments[first], segments[second], cos_limit):
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
