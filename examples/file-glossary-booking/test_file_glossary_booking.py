"""File-backed glossary booking example.

Demonstrates FileGlossary loading a Markdown glossary file, using the resulting
handles in story activities and t-string steps, and how term kinds are inferred
from activity-slot positions at session finish.

Key behaviours shown:
- g['Guest'] (slot 0 in a story activity) → kind inferred as actor.
- g['book'] (slot 1 in the second activity) → kind inferred as verb.
- g['Room'] (slot 2 in the second activity) → kind inferred as object.
- The first activity (Guest → 'browses' → 'listings') has only one glossary
  term, so it is excluded from coverage and renders "not coverage-tracked".
- 'receives' in the third activity is a bare verb (no glossary identity).
- g['Cancellation Policy'] is used ONLY in a t-string step, never in any story
  activity, so its kind stays None (kindless) and it renders with a neutral pill.
- 'Overbooking' is in the glossary file but referenced by no story and no step.
  It still appears in the generated glossary — every file term is included
  regardless of usage — under the neutral 'Other' section of the Glossary tab.
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

# Story: Guest → book (slot 1, verb) → Room (slot 2, object).
# The first activity is deliberately under-anchored — only one glossary term
# (Guest); 'browses' and 'listings' are bare words — so it is NOT coverage-tracked.
# 'receives' in the third activity is a bare verb the team hasn't promoted to a
# glossary term. 'Cancellation Policy' is never used in any activity (kindless).
book_a_room = story(
    'Book a Room',
    [
        activity(g['Guest'], 'browses', 'listings'),
        activity(g['Guest'], g['book']('books'), g['Room']),
        activity(g['Guest'], 'receives', g['Confirmation']),
    ],
)


@scenario('Guest books an available room', story=book_a_room)
def test_book_available_room():
    with given(t'the {g["Room"]} is available'):
        catalog = {'Standard': True, 'Suite': False}
    with when(t'{g["Guest"]} {g["book"]("books")} the {g["Room"]}'):
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
    with when(t'{g["Guest"]} {g["book"]("books")} a {g["Room"]}'):
        available_rooms = [name for name, avail in catalog.items() if avail]
    with then(t'no {g["Confirmation"]} is issued'):
        assert available_rooms == []
    # Deliberately use the kindless term only here in a t-string step:
    with then(  # 'Cancellation Policy' is kindless — neutral pill expected
        t'the {g["Cancellation Policy"]} does not apply'
    ):
        assert True
