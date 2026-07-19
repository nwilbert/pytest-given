"""Deterministic Domain-Storytelling-aware layout. Pure Python, no RNG.

Actors are pinned anchors: initiators (sources of numbered edges) on the left
band, pure recipients on the right, ordered by first appearance. Per-activity
work objects are seeded around their anchors and relaxed with springs (rest
length IDEAL_EDGE) plus pairwise repulsion below MIN_NODE_DIST.
"""

from __future__ import annotations

import math

from .graph import DiagramGraph

MARGIN = 90.0
BAND_X_LEFT = 150.0
BAND_X_RIGHT_INSET = 170.0  # right band sits at width - this
BAND_ROW_SPACING = 230.0  # must stay > MIN_NODE_DIST
IDEAL_EDGE = 265.0
MIN_NODE_DIST = 215.0
ITERATIONS = 140


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
