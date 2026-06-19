"""File-backed glossary booking example.

Demonstrates FileGlossary loading a Markdown glossary file, using the resulting
handles in story activities and t-string steps, and how term kinds are inferred
from activity-slot positions at session finish.

Key behaviours shown:
- g['Guest'] (slot 0 in the story activity) → kind inferred as actor.
- g['Book'] (slot 1 in the story activity) → kind inferred as verb.
- g['Room'] (slot 2 in the story activity) → kind inferred as object.
- g['Cancellation Policy'] is used ONLY in a t-string step, never in any story
  activity, so its kind stays None (kindless) and it renders with a neutral pill.
"""

from pathlib import Path

from pytest_given import (
    FileGlossary,
    activity,
    given,
    scenario,
    story,
    then,
    when,
)

# Load the glossary from the Markdown file alongside this module.
# Module-level declaration registers it with the plugin for kind inference.
g = FileGlossary(Path(__file__).parent / 'file-glossary-booking.md')

# Story: Guest → Book (slot 1, verb) → Room (slot 2, object).
# 'Confirmation' appears at slot 2 in the second activity (object).
# 'Cancellation Policy' is NEVER referenced in any activity (deliberately kindless).
book_a_room = story(
    'Book a Room',
    [
        activity(g['Guest'], g['Book']('books'), g['Room']),
        activity(g['Guest'], g['Book']('receives'), g['Confirmation']),
    ],
)


@scenario('Guest books an available room', story=book_a_room)
def test_book_available_room():
    with given(t'the {g["Room"]} is available'):
        catalog = {'Standard': True, 'Suite': False}
    with when(t'{g["Guest"]} {g["Book"]("books")} the {g["Room"]}'):
        booked_room = next(name for name, avail in catalog.items() if avail)
    with then(t'the {g["Guest"]} receives a {g["Confirmation"]}'):
        assert booked_room == 'Standard'
    # Deliberately use the kindless term only here in a t-string step:
    with then(  # 'Cancellation Policy' is kindless — neutral pill expected
        t'the {g["Cancellation Policy"]} applies to the {g["Room"]}'
    ):
        assert booked_room is not None


@scenario('Guest cannot book an unavailable room', story=book_a_room)
def test_book_unavailable_room():
    with given(t'no {g["Room"]} is available'):
        catalog = {'Suite': False}
    with when(t'{g["Guest"]} {g["Book"]("books")} a {g["Room"]}'):
        available_rooms = [name for name, avail in catalog.items() if avail]
    with then(t'no {g["Confirmation"]} is issued'):
        assert available_rooms == []
    # Deliberately use the kindless term only here in a t-string step:
    with then(  # 'Cancellation Policy' is kindless — neutral pill expected
        t'the {g["Cancellation Policy"]} does not apply'
    ):
        assert True
