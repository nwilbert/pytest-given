"""Deterministic Domain-Storytelling-aware layout. Pure Python, no RNG.

Actors are pinned anchors: initiators (sources of numbered edges) on the left
band, pure recipients on the right, ordered by first appearance. Per-activity
work objects are seeded around their anchors and relaxed with springs (rest
length IDEAL_EDGE) plus pairwise repulsion below MIN_NODE_DIST.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .graph import DiagramEdge, DiagramGraph, DiagramNode

MARGIN = 90.0
BAND_X_LEFT = 150.0
BAND_X_RIGHT_INSET = 170.0  # right band sits at width - this
BAND_ROW_SPACING = 270.0  # must stay > MIN_NODE_DIST
IDEAL_EDGE = 260.0
MIN_NODE_DIST = 250.0
ITERATIONS = 140
SEPARATION_ROUNDS = 60
SEPARATION_RING_CANDIDATES = 24

NODE_HALF_W = 62.0
NODE_HALF_H = 58.0
TRIM_SOURCE = 56.0
TRIM_TARGET = 64.0
LABEL_CHAR_W = 7.0
LABEL_H = 20.0
BADGE_W = 30.0
LABEL_OFFSET = 18.0
LOOP_RADIUS = 46.0


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
    initiators, recipients = _band_actors(graph)
    width, height = _canvas_size(len(initiators), len(recipients), len(graph.nodes))
    positions: dict[str, tuple[float, float]] = {}
    _place_band(positions, initiators, BAND_X_LEFT, height)
    _place_band(positions, recipients, width - BAND_X_RIGHT_INSET, height)
    _seed_work_objects(graph, positions, width, height)
    _relax(graph, positions, width, height)
    _separate(graph, positions, width, height)
    return positions, width, height


def _band_actors(graph: DiagramGraph) -> tuple[list[str], list[str]]:
    """Split actor node ids into initiators / pure recipients, each ordered by
    first appearance in the edge list (== first activity number, since
    activities are walked in order)."""
    actor_ids = {n.id for n in graph.nodes if n.glyph == 'actor'}
    initiator_set = {
        e.source for e in graph.edges if e.number is not None and e.source in actor_ids
    }
    ordered: list[str] = []
    for edge in graph.edges:
        for node_id in (edge.source, edge.target):
            if node_id in actor_ids and node_id not in ordered:
                ordered.append(node_id)
    for node in graph.nodes:  # actors never touched by an edge (defensive)
        if node.id in actor_ids and node.id not in ordered:
            ordered.append(node.id)
    initiators = [a for a in ordered if a in initiator_set]
    recipients = [a for a in ordered if a not in initiator_set]
    return initiators, recipients


def _canvas_size(
    initiator_count: int, recipient_count: int, node_count: int
) -> tuple[float, float]:
    rows = max(initiator_count, recipient_count, 1)
    height = max(620.0, 2 * (MARGIN + 110.0) + BAND_ROW_SPACING * (rows - 1))
    width = max(1080.0, 640.0 + 55.0 * node_count)
    return width, height


def _place_band(
    positions: dict[str, tuple[float, float]],
    band: list[str],
    band_x: float,
    height: float,
) -> None:
    if not band:
        return
    if len(band) == 1:
        positions[band[0]] = (band_x, height / 2)
        return
    top = MARGIN + 110.0
    step = (height - 2 * (MARGIN + 110.0)) / (len(band) - 1)
    assert len(band) == 1 or step >= MIN_NODE_DIST
    for index, node_id in enumerate(band):
        positions[node_id] = (band_x, top + index * step)


def _neighbours(graph: DiagramGraph) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for edge in graph.edges:
        if edge.source == edge.target:
            continue  # self-loops exert no layout force
        out[edge.source].append(edge.target)
        out[edge.target].append(edge.source)
    return out


def _seed_work_objects(
    graph: DiagramGraph,
    positions: dict[str, tuple[float, float]],
    width: float,
    height: float,
) -> None:
    """Seed in node insertion order (== path order), so a chained work object's
    predecessor is always placed first. Satellites (one placed neighbour) fan
    around their anchor at IDEAL_EDGE, biased toward the canvas centre."""
    nbrs = _neighbours(graph)
    satellite_count: dict[str, int] = {}
    for node in graph.nodes:
        if node.glyph != 'work':
            continue
        placed_ids = [m for m in nbrs[node.id] if m in positions]
        if placed_ids:
            cx = sum(positions[m][0] for m in placed_ids) / len(placed_ids)
            cy = sum(positions[m][1] for m in placed_ids) / len(placed_ids)
        else:
            cx, cy = width / 2, height / 2
        if len(placed_ids) == 1:
            anchor = placed_ids[0]
            fan_index = satellite_count.get(anchor, 0)
            satellite_count[anchor] = fan_index + 1
            toward_centre = math.atan2(height / 2 - cy, width / 2 - cx)
            angle = toward_centre + math.radians(-115.0 + fan_index * 68.0)
            cx += IDEAL_EDGE * math.cos(angle)
            cy += IDEAL_EDGE * math.sin(angle)
        positions[node.id] = (cx, cy)


def _relax(
    graph: DiagramGraph,
    positions: dict[str, tuple[float, float]],
    width: float,
    height: float,
) -> None:
    nbrs = _neighbours(graph)
    movable = {n.id for n in graph.nodes if n.glyph == 'work'}
    node_ids = [n.id for n in graph.nodes]
    for _ in range(ITERATIONS):
        force: dict[str, list[float]] = {i: [0.0, 0.0] for i in node_ids}
        for node_id in movable:
            for other in nbrs[node_id]:
                dx = positions[other][0] - positions[node_id][0]
                dy = positions[other][1] - positions[node_id][1]
                dist = math.hypot(dx, dy) or 1.0
                pull = (dist - IDEAL_EDGE) / dist * 0.08
                force[node_id][0] += dx * pull
                force[node_id][1] += dy * pull
        for index, id_a in enumerate(node_ids):
            for id_b in node_ids[index + 1 :]:
                dx = positions[id_b][0] - positions[id_a][0]
                dy = positions[id_b][1] - positions[id_a][1]
                dist = math.hypot(dx, dy) or 1.0
                if dist < MIN_NODE_DIST:
                    push = (MIN_NODE_DIST - dist) / dist * 0.45
                    if id_a in movable:
                        force[id_a][0] -= dx * push
                        force[id_a][1] -= dy * push
                    if id_b in movable:
                        force[id_b][0] += dx * push
                        force[id_b][1] += dy * push
        for node_id in movable:
            new_x = positions[node_id][0] + force[node_id][0]
            new_y = positions[node_id][1] + force[node_id][1]
            positions[node_id] = (
                min(max(new_x, MARGIN), width - MARGIN),
                min(max(new_y, MARGIN), height - MARGIN),
            )


def _separate(
    graph: DiagramGraph,
    positions: dict[str, tuple[float, float]],
    width: float,
    height: float,
) -> None:
    """Deterministic post-relaxation pass enforcing pairwise MIN_NODE_DIST.

    Spring/repulsion equilibria can leave pairs closer than MIN_NODE_DIST in
    ways a naive "push straight along the connecting line" cannot resolve on
    its own: a work node pulled toward two actors that happen to share an
    axis settles on a symmetric saddle point equidistant from both (pushing
    away from either one pushes it toward the other); and a satellite work
    node seeded near a canvas corner can find its only "away from the
    anchor" direction runs straight into the margin, so it presses into the
    corner every round without ever gaining distance.

    Each round first computes, in graph.nodes order, the axis-aligned
    full-deficit correction for every violating pair -- split evenly
    between two movable work nodes, applied wholly to the movable side
    against a pinned actor. For each movable node still in violation, that
    direct correction is then compared against SEPARATION_RING_CANDIDATES
    points spaced evenly around a circle of radius MIN_NODE_DIST, tried
    centred on each distinct conflicting neighbour's own position as well as
    their mean; whichever candidate leaves the smallest total remaining
    violation (summed squared deficit against every other node) is kept. A
    ring centred on a single neighbour is guaranteed clear of that neighbour
    specifically -- needed when a node's conflicts are two unrelated nodes
    that only happen to be near each other (the mean of their positions can
    sit somewhere that clears neither); the mean-centred ring stays useful
    for the genuinely shared-anchor case (two actors on the same axis) a
    single neighbour's ring can't distinguish from. The ring lets a node
    walk around a pinned anchor instead of stalling against a corner. Runs
    up to SEPARATION_ROUNDS rounds, stopping as soon as a round finds no
    violation.
    """
    movable = {n.id for n in graph.nodes if n.glyph == 'work'}
    node_ids = [n.id for n in graph.nodes]

    def remaining_violation(candidate: tuple[float, float], excluded_id: str) -> float:
        total = 0.0
        for other_id in node_ids:
            if other_id == excluded_id:
                continue
            other_x, other_y = positions[other_id]
            dist = math.hypot(candidate[0] - other_x, candidate[1] - other_y)
            if dist < MIN_NODE_DIST:
                total += (MIN_NODE_DIST - dist) ** 2
        return total

    for _ in range(SEPARATION_ROUNDS):
        push: dict[str, list[float]] = {node_id: [0.0, 0.0] for node_id in node_ids}
        conflicts: dict[str, list[tuple[float, float]]] = {}
        any_violation = False
        for index, id_a in enumerate(node_ids):
            for id_b in node_ids[index + 1 :]:
                a_movable = id_a in movable
                b_movable = id_b in movable
                if not a_movable and not b_movable:
                    continue
                dx = positions[id_b][0] - positions[id_a][0]
                dy = positions[id_b][1] - positions[id_a][1]
                dist = math.hypot(dx, dy) or 1.0
                if dist >= MIN_NODE_DIST:
                    continue
                any_violation = True
                deficit = MIN_NODE_DIST - dist
                ux, uy = dx / dist, dy / dist
                share = deficit / 2 if (a_movable and b_movable) else deficit
                if a_movable:
                    push[id_a][0] -= ux * share
                    push[id_a][1] -= uy * share
                    conflicts.setdefault(id_a, []).append(positions[id_b])
                if b_movable:
                    push[id_b][0] += ux * share
                    push[id_b][1] += uy * share
                    conflicts.setdefault(id_b, []).append(positions[id_a])
        if not any_violation:
            break
        for node_id in node_ids:
            neighbours = conflicts.get(node_id)
            if neighbours is None:
                continue
            old_x, old_y = positions[node_id]
            push_x, push_y = push[node_id]
            best = (
                min(max(old_x + push_x, MARGIN), width - MARGIN),
                min(max(old_y + push_y, MARGIN), height - MARGIN),
            )
            best_score = remaining_violation(best, node_id)
            # Ring centres: each distinct conflicting neighbour's own position
            # (a ring here is guaranteed clear of *that* neighbour, which
            # matters when the conflicts are unrelated nodes that happen to
            # be near each other only by coincidence) plus their average
            # (which is the useful centre for the shared-anchor case the
            # single-neighbour ring can't distinguish from). Deduplicated so
            # a lone conflict doesn't evaluate the same ring twice.
            mean_x = sum(point[0] for point in neighbours) / len(neighbours)
            mean_y = sum(point[1] for point in neighbours) / len(neighbours)
            ring_centres = {(mean_x, mean_y), *neighbours}
            for centre_x, centre_y in ring_centres:
                for ring_index in range(SEPARATION_RING_CANDIDATES):
                    angle = 2 * math.pi * ring_index / SEPARATION_RING_CANDIDATES
                    candidate = (
                        min(
                            max(centre_x + MIN_NODE_DIST * math.cos(angle), MARGIN),
                            width - MARGIN,
                        ),
                        min(
                            max(centre_y + MIN_NODE_DIST * math.sin(angle), MARGIN),
                            height - MARGIN,
                        ),
                    )
                    score = remaining_violation(candidate, node_id)
                    if score < best_score:
                        best_score = score
                        best = candidate
            positions[node_id] = best


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
    for edge in graph.edges:
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
        # Distinct connected nodes should never coincide once _separate has
        # run; a zero distance here means two placed nodes with an edge
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
