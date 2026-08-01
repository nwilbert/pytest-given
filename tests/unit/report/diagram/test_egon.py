"""Tests for the egon.io (.egn) exporter — structure of the emitted document."""

from __future__ import annotations

import json

from pytest_given.model import ActivityId, StoryId
from pytest_given.report.diagram.egon import (
    DOCUMENT_SVG,
    PERSON_SVG,
    layout_to_egn,
)
from pytest_given.report.diagram.graph import DiagramEdge, DiagramGraph, DiagramNode
from pytest_given.report.diagram.layout import layout_graph


def _actor(node_id: str, label: str) -> DiagramNode:
    return DiagramNode(
        id=node_id, label=label, sublabel=None, glyph='actor', term_id=None
    )


def _work(node_id: str, label: str) -> DiagramNode:
    return DiagramNode(
        id=node_id, label=label, sublabel=None, glyph='work', term_id=None
    )


def _edge(source: str, target: str, label: str, number: int | None) -> DiagramEdge:
    return DiagramEdge(
        source=source,
        target=target,
        label=label,
        activity_id=ActivityId(number or 1),
        number=number,
        connective=number is None,
    )


def _sample_graph() -> DiagramGraph:
    # Carol -1 searches-> Room ; Carol -2 books-> Booking -to-> Guest
    nodes = (
        _actor('a:carol', 'Carol'),
        _work('w:room', 'Room'),
        _work('w:booking', 'Booking'),
        _actor('a:guest', 'Guest'),
    )
    edges = (
        _edge('a:carol', 'w:room', 'searches for', 1),
        _edge('a:carol', 'w:booking', 'books', 2),
        _edge('w:booking', 'a:guest', 'to', None),
    )
    return DiagramGraph(
        story_id=StoryId('book-a-room'), title='Book a Room', nodes=nodes, edges=edges
    )


def test_egn_has_domain_icons_and_versioned_trailer() -> None:
    egn = layout_to_egn(layout_graph(_sample_graph()))
    assert egn['domain']['actors']['Person'] == PERSON_SVG
    assert egn['domain']['workObjects']['Document'] == DOCUMENT_SVG
    # dst ends with an info blob and a version stamp egon.io recognises.
    assert egn['dst'][-2] == {'info': ''}
    assert egn['dst'][-1] == {'version': '2.0.1'}


def test_egn_shapes_carry_glyph_type_and_position() -> None:
    layout = layout_graph(_sample_graph())
    egn = layout_to_egn(layout)
    shapes = [
        item
        for item in egn['dst']
        if str(item.get('type', '')).endswith(('actorPerson', 'workObjectDocument'))
    ]
    assert len(shapes) == 4
    by_name = {shape['name']: shape for shape in shapes}
    assert by_name['Carol']['type'] == 'domainStory:actorPerson'
    assert by_name['Room']['type'] == 'domainStory:workObjectDocument'
    for shape in shapes:
        assert shape['id'].startswith('shape_')
        assert isinstance(shape['x'], int)
        assert isinstance(shape['y'], int)
        assert shape['$type'] == 'Element'


def test_egn_activities_reference_shapes_and_carry_numbers() -> None:
    layout = layout_graph(_sample_graph())
    egn = layout_to_egn(layout)
    shape_ids = {
        item['id']
        for item in egn['dst']
        if str(item.get('type', '')).startswith('domainStory:')
        and item.get('type') != 'domainStory:activity'
    }
    activities = [
        item for item in egn['dst'] if item.get('type') == 'domainStory:activity'
    ]
    assert len(activities) == 3
    by_name = {act['name']: act for act in activities}
    assert by_name['searches for']['number'] == 1
    assert by_name['books']['number'] == 2
    assert by_name['to']['number'] is None
    for act in activities:
        assert act['source'] in shape_ids
        assert act['target'] in shape_ids
        assert len(act['waypoints']) >= 2
        assert act['waypoints'][0]['original'] == {
            'x': act['waypoints'][0]['x'],
            'y': act['waypoints'][0]['y'],
        }


def test_egn_serialises_to_pretty_json() -> None:
    from pytest_given.report.diagram.egon import egn_to_json

    egn = layout_to_egn(layout_graph(_sample_graph()))
    text = egn_to_json(egn)
    assert json.loads(text) == egn  # round-trips
    assert '\n' in text  # pretty-printed
