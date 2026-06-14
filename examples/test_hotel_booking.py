"""Online Hotel Booking — showcases DDD glossary, Domain Story, and coverage."""

import pytest

from pytest_given import (
    Glossary,
    activity,
    draft,
    given,
    scenario,
    story,
    then,
    when,
)

# Domain vocabulary — the ubiquitous language for hotel bookings.
g = Glossary()

guest = g.actor('Guest', definition='Person booking accommodation.')
booking_system = g.actor(
    'Booking System', definition='Automated reservation system.'
)

room = g.work_object('Room', definition='A bookable hotel room.')
booking = g.work_object('Booking', definition='A reservation for a room.')
payment = g.work_object('Payment', definition='Money transferred for a booking.')
confirmation = g.work_object(
    'Confirmation', definition='Notification of a successful booking.'
)

search = g.verb('search', definition='Look up available options.')
select = g.verb('select', definition='Choose one option from a set.')
submit = g.verb('submit', definition='Send to the system for processing.')
confirm = g.verb('confirm', definition='Finalize and acknowledge.')
send = g.verb('send', definition='Deliver to a recipient.')


book_a_shared_room = story(
    'Book a Shared Room',
    activities=(
        activity(guest, search('searches for'), room),
        activity(guest('Alice'), select('selects'), room('Deluxe Suite')),
        activity(guest('Alice'), submit('submits'), payment),
        activity(
            booking_system,
            confirm('confirms'),
            booking,
            'for',
            guest('Alice'),
            'and',
            guest('Bob'),
        ),
        activity(booking_system, send('sends'), confirmation, 'to', guest('Alice')),
        activity(booking_system, send('sends'), confirmation, 'to', guest('Bob')),
        activity(
            guest('Alice'),
            draft.verb('redeems'),
            draft.work_object('loyalty bonus'),
        ),
    ),
)


@pytest.fixture
@given('our guest Alice')
def alice():
    return {'name': 'Alice', 'email': 'alice@example.com'}


@pytest.fixture
@given('our guest Bob')
def bob():
    return {'name': 'Bob', 'email': 'bob@example.com'}


@scenario('Alice books a shared room with Bob', story=book_a_shared_room)
def test_book_shared(alice, bob):
    with when(t'{guest("Alice")} {search("searches for")} a {room}'):
        pass
    with when(t'{guest("Alice")} {select("selects")} the {room("Deluxe Suite")}'):
        pass
    with when(t'{guest("Alice")} {submit("submits")} the {payment}'):
        pass
    with then(
        t'the {booking_system} {confirm("confirms")} the {booking} '
        t'for {guest("Alice")} and {guest("Bob")}'
    ):
        pass
    with then(
        t'the {booking_system} {send("sends")} a {confirmation} to {guest("Alice")}'
    ):
        pass
    with then(
        t'the {booking_system} {send("sends")} a {confirmation} to {guest("Bob")}'
    ):
        pass
