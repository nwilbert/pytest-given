"""Deterministic crossing-minimizing layout. Pure Python, no RNG.

The overriding rule is that drawn arrows must not overlap: no edge may cross
another edge, and (best effort) no edge may run over an unrelated node. Nodes
are placed on a column/row grid whose spacing is >= MIN_NODE_DIST, so nodes can
never overlap by construction. Columns come from a longest-path layering of the
activity flow (sources -- the actors and objects that start a path -- on the
left, each step one column further right); within a column the row order is
first seeded by the barycentre heuristic and then polished by a local search
that directly minimizes the true straight-line crossing count. A second search
pass then reorders rows (never columns, so the diagram stays as compact) to
pull consecutively numbered activities together and to sweep each actor's
numbered spokes clockwise (low number to high) -- strict secondary goals that
can never cost a crossing. Vertical compactness is not weighted: the diagrams
page owns "fit to screen" through zoom, so a wider or taller diagram is fine.
Finally the whole diagram is reflected (an isometry, so crossings and step
spacing are untouched) to seat the story's start node in the top-left corner
-- the third priority. Edge endpoints are trimmed back to the node rims and
each edge's label is slid along it until it clears every node and previously
placed label.
"""

from __future__ import annotations

import itertools
import math
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass

from .graph import DiagramEdge, DiagramGraph, DiagramNode

MARGIN = 90.0
COL_SPACING = 320.0  # horizontal gap between layers; must stay > MIN_NODE_DIST
ROW_SPACING = 260.0  # vertical gap between rows;    must stay > MIN_NODE_DIST
MIN_NODE_DIST = 250.0
PAD = 180.0  # canvas padding around the outermost node centres
MIN_CANVAS_W = 1080.0
MIN_CANVAS_H = 620.0
BARYCENTRE_SWEEPS = 6
SEARCH_ROUNDS = 40
SLOT_MARGIN = 2  # empty slots to probe above/below a layer during local search

assert COL_SPACING >= MIN_NODE_DIST
assert ROW_SPACING >= MIN_NODE_DIST

NODE_HALF_W = 62.0
NODE_HALF_H = 58.0
TRIM_SOURCE = 56.0
TRIM_TARGET = 64.0
LABEL_CHAR_W = 7.0
LABEL_H = 20.0
BADGE_W = 30.0
LABEL_OFFSET = 18.0
LOOP_RADIUS = 46.0

# Local-search cost weights, ranked by magnitude so each objective only ever
# breaks ties left by the one above it: avoid crossings first, then edges
# running over nodes, then keep consecutively numbered steps near each other
# (so the eye follows 1 -> 2 -> 3), then sweep each actor's numbered spokes
# clockwise, then stay short. Compactness is intentionally disabled -- zoom
# owns "fit to screen".
CROSSING_COST = 1_000_000_000.0
NODE_ON_EDGE_COST = 1_000_000.0
SEQUENCE_COST = 5.0  # per column-width between consecutive numbered edges
CLOCKWISE_COST = 2.0  # per counter-clockwise turn within an actor's fan
# Compactness is deliberately unweighted: "fit to screen" is owned by the
# diagrams page's zoom controls, not the layout, so a readability objective
# (clockwise fans) is never vetoed to keep a diagram short. Kept as a named
# zero so the ranking comment and any future re-enable stay legible.
HEIGHT_COST = 0.0  # per row of total vertical span (disabled; see above)
LENGTH_COST = 0.001
COLLINEAR_DEG = 8.0  # two edges from a shared node this close in angle overlap
NODE_ON_EDGE_CLEARANCE = 70.0  # how near a segment a foreign node may sit


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
    index_of = {node_id: i for i, node_id in enumerate(node_ids)}
    directed = _directed_edges(graph)
    sequence = _numbered_sequence(graph)
    fans = _actor_fans(graph)
    undirected = _undirected_adjacency(node_ids, directed)
    layer_of = _assign_layers(node_ids, directed)
    layer_nodes = _order_within_layers(node_ids, index_of, undirected, layer_of)
    cell_of = _seed_cells(layer_nodes)
    cell_of = _local_search(node_ids, index_of, directed, sequence, fans, cell_of)
    grid = {
        node_id: (column * COL_SPACING, row * ROW_SPACING)
        for node_id, (column, row) in cell_of.items()
    }
    positions, width, height = _framed(grid)
    start = sequence[0][0] if sequence else None
    positions = _orient_start_top_left(positions, width, height, start)
    return positions, width, height


def _orient_start_top_left(
    positions: dict[str, tuple[float, float]],
    width: float,
    height: float,
    start: str | None,
) -> dict[str, tuple[float, float]]:
    """Third priority: the story should read from the top-left. Reflecting the
    whole diagram horizontally and/or vertically is an isometry -- it preserves
    every edge crossing and every distance between numbered steps -- so among
    the four axis-aligned reflections we simply keep the one that lands the
    story's start node (activity 1's initiator) nearest the top-left corner.
    This never costs a crossing or loosens the sequence grouping."""
    if start is None or start not in positions:
        return positions
    start_x, start_y = positions[start]
    flips = [(False, False), (True, False), (False, True), (True, True)]

    def corner_distance(flip: tuple[bool, bool]) -> float:
        flip_x, flip_y = flip
        return (width - start_x if flip_x else start_x) + (
            height - start_y if flip_y else start_y
        )

    flip_x, flip_y = min(
        flips, key=lambda flip: (corner_distance(flip), flips.index(flip))
    )
    if not flip_x and not flip_y:
        return positions
    return {
        node_id: (
            width - x if flip_x else x,
            height - y if flip_y else y,
        )
        for node_id, (x, y) in positions.items()
    }


def _directed_edges(graph: DiagramGraph) -> list[tuple[str, str]]:
    """Distinct non-self edges in first-appearance order (parallel duplicates
    collapse, self-loops exert no layout force)."""
    seen: set[tuple[str, str]] = set()
    directed: list[tuple[str, str]] = []
    for edge in graph.edges:
        pair = (edge.source, edge.target)
        if edge.source == edge.target or pair in seen:
            continue
        seen.add(pair)
        directed.append(pair)
    return directed


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


def _undirected_adjacency(
    node_ids: list[str], directed: list[tuple[str, str]]
) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for source, target in directed:
        adjacency[source].append(target)
        adjacency[target].append(source)
    return adjacency


def _assign_layers(
    node_ids: list[str], directed: list[tuple[str, str]]
) -> dict[str, int]:
    """Longest-path layering. Back edges (found by DFS) are dropped so the
    layering runs on a DAG even when activities form a directed cycle across
    work objects; the dropped edges still count for crossings, just not for
    the column each node lands in."""
    out_adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for source, target in directed:
        out_adjacency[source].append(target)

    colour = dict.fromkeys(node_ids, 0)  # 0 white, 1 grey, 2 black
    forward: list[tuple[str, str]] = []
    for start in node_ids:
        if colour[start] != 0:
            continue
        colour[start] = 1
        stack: list[tuple[str, Iterator[str]]] = [(start, iter(out_adjacency[start]))]
        while stack:
            node, neighbours = stack[-1]
            advanced = False
            for nxt in neighbours:
                if colour[nxt] == 0:
                    forward.append((node, nxt))
                    colour[nxt] = 1
                    stack.append((nxt, iter(out_adjacency[nxt])))
                    advanced = True
                    break
                if colour[nxt] == 2:  # forward/cross edge: keeps the DAG acyclic
                    forward.append((node, nxt))
                # grey neighbour == back edge, drop it
            if not advanced:
                colour[node] = 2
                stack.pop()

    forward_adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    indegree = dict.fromkeys(node_ids, 0)
    for source, target in forward:
        forward_adjacency[source].append(target)
        indegree[target] += 1
    queue = deque(node_id for node_id in node_ids if indegree[node_id] == 0)
    layer = dict.fromkeys(node_ids, 0)
    while queue:
        node = queue.popleft()
        for target in forward_adjacency[node]:
            layer[target] = max(layer[target], layer[node] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return layer


def _order_within_layers(
    node_ids: list[str],
    index_of: dict[str, int],
    undirected: dict[str, list[str]],
    layer_of: dict[str, int],
) -> dict[int, list[str]]:
    """Seed each layer's row order by node insertion order, then run
    alternating barycentre sweeps to line neighbours up across columns."""
    max_layer = max(layer_of.values())
    layer_nodes: dict[int, list[str]] = {index: [] for index in range(max_layer + 1)}
    for node_id in node_ids:
        layer_nodes[layer_of[node_id]].append(node_id)
    order_index = dict.fromkeys(node_ids, 0)

    def reindex(layer: int) -> None:
        for position, node_id in enumerate(layer_nodes[layer]):
            order_index[node_id] = position

    for layer in layer_nodes:
        reindex(layer)

    for sweep in range(BARYCENTRE_SWEEPS):
        downward = sweep % 2 == 0
        layers = range(1, max_layer + 1) if downward else range(max_layer - 1, -1, -1)
        neighbour_layer_delta = -1 if downward else 1
        for layer in layers:

            def barycentre(node_id: str, delta: int = neighbour_layer_delta) -> float:
                neighbours = [
                    other
                    for other in undirected[node_id]
                    if layer_of[other] == layer_of[node_id] + delta
                ]
                if not neighbours:
                    return float(order_index[node_id])
                return sum(order_index[other] for other in neighbours) / len(neighbours)

            layer_nodes[layer].sort(
                key=lambda node_id: (barycentre(node_id), index_of[node_id])
            )
            reindex(layer)
    return layer_nodes


def _seed_cells(layer_nodes: dict[int, list[str]]) -> dict[str, tuple[int, int]]:
    """Turn the ordered layers into integer (column, row) grid cells, each
    layer vertically centred on row 0."""
    cell_of: dict[str, tuple[int, int]] = {}
    for column, nodes in layer_nodes.items():
        count = len(nodes)
        for position, node_id in enumerate(nodes):
            cell_of[node_id] = (column, position - (count - 1) // 2)
    return cell_of


def _local_search(
    node_ids: list[str],
    index_of: dict[str, int],
    directed: list[tuple[str, str]],
    sequence: list[tuple[str, str]],
    fans: list[tuple[str, tuple[str, ...]]],
    cell_of: dict[str, tuple[int, int]],
) -> dict[str, tuple[int, int]]:
    """Polish the barycentre seed by directly minimizing the true straight-line
    crossing cost. Nodes live on distinct integer grid cells; moves are a swap
    of any two nodes' cells and a relocation into a free cell in an adjacent
    column. Both are accepted only when they strictly lower the cost, so the
    search is a deterministic monotone descent -- every candidate is tried in a
    fixed order and ties never displace the incumbent.

    Two phases: the first ignores the sequence term and drives crossings and
    grazes to their minimum; the second adds the sequence term to line the
    numbered steps up in reading order. Because a crossing outweighs every
    sequence gain, the second phase can never trade a crossing away -- it only
    improves the ordering within the crossing-free arrangement phase one found.
    """
    ordered = sorted(node_ids, key=lambda node_id: index_of[node_id])

    def descend(with_sequence: bool, allow_column_moves: bool) -> None:
        chain = sequence if with_sequence else []
        active_fans = fans if with_sequence else []

        def cost() -> float:
            return _layout_cost(node_ids, directed, chain, active_fans, cell_of)

        current = cost()
        for _ in range(SEARCH_ROUNDS):
            improved = False
            for first in range(len(ordered)):
                for second in range(first + 1, len(ordered)):
                    node_a, node_b = ordered[first], ordered[second]
                    cell_of[node_a], cell_of[node_b] = (
                        cell_of[node_b],
                        cell_of[node_a],
                    )
                    candidate = cost()
                    if candidate < current - 1e-6:
                        current = candidate
                        improved = True
                    else:
                        cell_of[node_a], cell_of[node_b] = (
                            cell_of[node_b],
                            cell_of[node_a],
                        )
            occupied = set(cell_of.values())
            rows = [row for _, row in cell_of.values()]
            low, high = min(rows) - SLOT_MARGIN, max(rows) + SLOT_MARGIN
            for node_id in ordered:
                origin = cell_of[node_id]
                column, _row = origin
                columns = (
                    (column - 1, column, column + 1)
                    if allow_column_moves
                    else (column,)
                )
                for target in _candidate_cells(columns, low, high, occupied):
                    cell_of[node_id] = target
                    candidate = cost()
                    if candidate < current - 1e-6:
                        current = candidate
                        improved = True
                        occupied.discard(origin)
                        occupied.add(target)
                        break
                    cell_of[node_id] = origin
            if not improved:
                break

    # Phase 1 minimizes crossings/grazes with full freedom; phase 2 layers in
    # the sequence term but only reorders rows within phase 1's columns, so it
    # tidies the reading order without widening the diagram.
    descend(with_sequence=False, allow_column_moves=True)
    descend(with_sequence=True, allow_column_moves=False)
    return cell_of


def _candidate_cells(
    columns: tuple[int, ...], low: int, high: int, occupied: set[tuple[int, int]]
) -> list[tuple[int, int]]:
    return [
        (candidate_column, row)
        for candidate_column in columns
        for row in range(low, high + 1)
        if (candidate_column, row) not in occupied
    ]


def _layout_cost(
    node_ids: list[str],
    directed: list[tuple[str, str]],
    sequence: list[tuple[str, str]],
    fans: list[tuple[str, tuple[str, ...]]],
    cell_of: dict[str, tuple[int, int]],
) -> float:
    position = {
        node_id: (column * COL_SPACING, row * ROW_SPACING)
        for node_id, (column, row) in cell_of.items()
    }
    segments = [
        (position[source], position[target], source, target)
        for source, target in directed
    ]
    crossings = _count_overlaps(segments)
    grazes = 0
    total_length = 0.0
    for start, end, source, target in segments:
        total_length += math.hypot(end[0] - start[0], end[1] - start[1])
        for node_id in node_ids:
            if node_id in (source, target):
                continue
            if _point_near_segment(
                position[node_id], start, end, NODE_ON_EDGE_CLEARANCE
            ):
                grazes += 1
    rows = [row for _, row in cell_of.values()]
    row_span = max(rows) - min(rows)
    return (
        crossings * CROSSING_COST
        + grazes * NODE_ON_EDGE_COST
        + _sequence_spread(sequence, position) * SEQUENCE_COST
        + _clockwise_disorder(fans, position) * CLOCKWISE_COST
        + row_span * HEIGHT_COST
        + total_length * LENGTH_COST
    )


def _sequence_spread(
    sequence: list[tuple[str, str]], position: dict[str, tuple[float, float]]
) -> float:
    """Total gap, in column-widths, between the midpoints of consecutively
    numbered activity edges. Minimizing it lines the numbered steps up in
    reading order."""
    midpoints = [
        (
            (position[source][0] + position[target][0]) / 2,
            (position[source][1] + position[target][1]) / 2,
        )
        for source, target in sequence
    ]
    return sum(
        math.hypot(later[0] - earlier[0], later[1] - earlier[1]) / COL_SPACING
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
        label = _slide_label(edge, x1, y1, x2, y2, ux, uy, obstacles)
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
) -> LabelBox:
    """Place the label near the edge midpoint, offset perpendicular; slide it
    along the edge (alternating around the midpoint) until it clears all
    obstacle boxes. A short edge between two crowded nodes can leave every
    in-line slide position clipping one of its own endpoints' boxes (the
    perpendicular offset is much smaller than a node's radius), so the
    search retries the same slide fractions at a larger perpendicular
    offset -- still within LABEL_OFFSET + LABEL_H, the "stays near its edge"
    bound other code relies on -- and on the opposite side of the line too
    (the crowded node is often on just one side; the fixed offset direction
    used by a single-sided search can point straight at it) before falling
    back to the least-overlapping candidate seen across every combination."""
    best: LabelBox | None = None
    best_overlap = math.inf
    for side in (1.0, -1.0):
        for offset in (LABEL_OFFSET, LABEL_OFFSET + LABEL_H - 1.0):
            for attempt in range(13):
                step = (attempt + 1) // 2 * 0.08
                fraction = 0.5 + (step if attempt % 2 == 1 else -step)
                centre_x = x1 + (x2 - x1) * fraction - uy * offset * side
                centre_y = y1 + (y2 - y1) * fraction + ux * offset * side
                candidate = _label_box(edge, centre_x, centre_y)
                overlap = sum(_overlap_area(candidate, box) for box in obstacles)
                if overlap == 0.0:
                    return candidate
                if overlap < best_overlap:
                    best, best_overlap = candidate, overlap
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
