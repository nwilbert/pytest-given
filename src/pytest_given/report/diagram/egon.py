"""A laid-out story as an egon.io (Domain Story Modeler) `.egn` file.

The file carries our layout, so a modeller can open it at https://egon.io/ and
rearrange it by hand. egon.io reads its own export format, v2.0.1: an icon
dictionary, then a `dst` array of shapes and activities ending in an `info`
and a `version` entry. Every actor gets egon's Person icon and every work
object its Document icon, which the modeller can swap there.
"""

# No `__lazy_modules__`: the `BaseModel` subclasses below import Pydantic as
# this module loads.

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from .layout import DiagramLayout, PlacedEdge, PlacedNode

EGN_VERSION: Final = '2.0.1'

# egon.io's own Person and Document icons, so the file needs no other.
PERSON_SVG: Final = (
    '<svg viewBox="0 0 24 26" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 5.9c1.16 0 2.1.94 2.1 2.1s-.94 2.1-2.1 2.1S9.9 9.16 9.9 8s.94-2.1 '
    '2.1-2.1m0 9c2.97 0 6.1 1.46 6.1 2.1v1.1H5.9V17c0-.64 3.13-2.1 6.1-2.1M12 4C9.79 '
    '4 8 5.79 8 8s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm0 9c-2.67 0-8 1.34-8 4v3h16v-3c0'
    '-2.66-5.33-4-8-4z"/><path d="M0 0h24v24H0z" fill="none"/></svg>'
)
DOCUMENT_SVG: Final = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
    'viewBox="0 0 24 26"><path fill="none" d="M0 0h24v24H0V0z"/><path d="M8 16h8v2H8'
    'zm0-4h8v2H8zm6-10H6c-1.1 0-2 .9-2 2v16c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6'
    '-6zm4 18H6V4h7v5h5v11z"/></svg>'
)

# egon.io places a shape by its top-left corner and draws it in a fixed box,
# so a node's centre moves up and left by half that box.
_ICON_HALF: Final = 38


def render_egn(layout: DiagramLayout) -> str:
    shape_ids = {
        placed.node.id: f'shape_{index:04d}'
        for index, placed in enumerate(layout.nodes, start=1)
    }
    numbers = [placed.edge.number for placed in layout.edges]
    document = _EgnDocument(
        domain=_Domain(),
        dst=[
            *(_shape(placed, shape_ids[placed.node.id]) for placed in layout.nodes),
            *(
                _activity(
                    placed,
                    f'connection_{index:04d}',
                    shape_ids,
                    shared_number=numbers.count(placed.edge.number) > 1,
                )
                for index, placed in enumerate(layout.edges, start=1)
            ),
            _Info(),
            _Version(),
        ],
    )
    return document.model_dump_json(indent=2, by_alias=True)


class _EgnModel(BaseModel):
    # Fields in egon.io's own key order, so a file it saves back diffs cleanly.
    model_config = ConfigDict(frozen=True)


class _Empty(_EgnModel):
    pass


class _Point(_EgnModel):
    x: int
    y: int


class _Waypoint(_EgnModel):
    original: _Point
    x: int
    y: int


class _Shape(_EgnModel):
    type: Literal['domainStory:actorPerson', 'domainStory:workObjectDocument']
    name: str
    id: str
    picked_color: Literal['black'] = Field(
        default='black', serialization_alias='pickedColor'
    )
    x: int
    y: int
    element_type: Literal['Element'] = Field(
        default='Element', serialization_alias='$type'
    )
    di: _Empty = _Empty()
    descriptor: _Empty = Field(default=_Empty(), serialization_alias='$descriptor')


class _Activity(_EgnModel):
    type: Literal['domainStory:activity'] = 'domainStory:activity'
    name: str
    id: str
    picked_color: Literal['black'] = Field(
        default='black', serialization_alias='pickedColor'
    )
    number: int | None
    waypoints: tuple[_Waypoint, _Waypoint]
    source: str
    target: str
    element_type: Literal['Element'] = Field(
        default='Element', serialization_alias='$type'
    )
    di: _Empty = _Empty()
    descriptor: _Empty = Field(default=_Empty(), serialization_alias='$descriptor')
    # Only a numbered activity says whether its number repeats.
    multiple_number_allowed: bool | None = Field(
        default=None,
        serialization_alias='multipleNumberAllowed',
        exclude_if=lambda value: value is None,
    )


class _Info(_EgnModel):
    info: str = ''


class _Version(_EgnModel):
    version: str = EGN_VERSION


class _Domain(_EgnModel):
    name: str = 'default'
    actors: dict[str, str] = {'Person': PERSON_SVG}
    work_objects: dict[str, str] = Field(
        default={'Document': DOCUMENT_SVG}, serialization_alias='workObjects'
    )


class _EgnDocument(_EgnModel):
    domain: _Domain
    dst: list[_Shape | _Activity | _Info | _Version]


def _shape(placed: PlacedNode, shape_id: str) -> _Shape:
    return _Shape(
        type=(
            'domainStory:actorPerson'
            if placed.node.glyph == 'actor'
            else 'domainStory:workObjectDocument'
        ),
        name=placed.node.label,
        id=shape_id,
        x=round(placed.x) - _ICON_HALF,
        y=round(placed.y) - _ICON_HALF,
    )


def _activity(
    placed: PlacedEdge,
    connection_id: str,
    shape_ids: dict[str, str],
    shared_number: bool,
) -> _Activity:
    edge = placed.edge
    return _Activity(
        name=edge.label,
        id=connection_id,
        number=edge.number,
        waypoints=(_waypoint(placed.x1, placed.y1), _waypoint(placed.x2, placed.y2)),
        source=shape_ids[edge.source],
        target=shape_ids[edge.target],
        multiple_number_allowed=shared_number if edge.number is not None else None,
    )


def _waypoint(x: float, y: float) -> _Waypoint:
    point = _Point(x=round(x), y=round(y))
    return _Waypoint(original=point, x=point.x, y=point.y)
