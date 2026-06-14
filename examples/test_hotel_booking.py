"""Group hotel booking — showcases DDD glossary, Domain Story, and coverage.

An Organizer (Carol) reserves rooms for her colleagues Alice and Bob ahead of a
conference. The Story covers seven activities exercising every part of the
domain-storytelling grammar: canonical entities, actor/work-object instances,
two work objects joined by a preposition, two actors in the same path,
multi-path activities for parallel branches, and a draft activity for in-flight
vocabulary.

Three scenarios implement the Story at varying detail, each in full
Given/When/Then form:

* `test_pick_suite` — happy path, covers activities 1–2.
* `test_complete_booking` — happy path through the rest, covers 2–6.
  Activity 2 is intentionally shared with `test_pick_suite` so the Stories tab
  shows two badges on that row.
* `test_payment_declined` — parameterized error branch using a `reject` verb
  that lives in the glossary but isn't part of any story activity. Cases pair
  a payment method with its decline reason (credit card / insufficient funds,
  debit card / expired card, bank transfer / fraud check), all funneling
  through the same reject path. Covers 3 and 4, overlapping with
  `test_complete_booking` to show how a scenario can probe a different aspect
  (the failure path) of the same activities.

Activity 7 stays uncovered (drafts are excluded from implicit coverage), making
visible the vocabulary the team still has to commit.
"""

import pytest

from pytest_given import (
    Glossary,
    activity,
    draft,
    given,
    path,
    scenario,
    story,
    then,
    when,
)

# Ubiquitous language for group bookings.
g = Glossary()

organizer = g.actor(
    'Organizer', definition='Person booking accommodation on behalf of a group.'
)
guest = g.actor('Guest', definition='Individual traveler in the group.')
booking_system = g.actor(
    'Booking System', definition='Automated reservation back-end.'
)

room = g.work_object('Room', definition='A bookable hotel room.')
booking = g.work_object('Booking', definition='A reservation for one or more rooms.')
payment = g.work_object('Payment', definition='Money transferred for a booking.')
confirmation = g.work_object(
    'Confirmation', definition='Notification of a successful booking.'
)

search = g.verb('search', definition='Look up available options.')
select = g.verb('select', definition='Choose one option from a set.')
add = g.verb('add', definition='Attach a member to a collection.')
submit = g.verb('submit', definition='Send to the system for processing.')
confirm = g.verb('confirm', definition='Finalize and acknowledge.')
send = g.verb('send', definition='Deliver to a recipient.')
# `reject` is in the ubiquitous language but no Story activity uses it yet —
# it surfaces in the Glossary tab and powers the error-path scenario.
reject = g.verb('reject', definition='Refuse to process or accept.')


book_a_group_trip = story(
    'Book a Group Trip',
    [
        # 1. Canonical actor + canonical work object.
        activity(organizer, search('searches for'), room),
        # 2. Actor instance + work-object instance.
        activity(organizer('Carol'), select('selects'), room('Deluxe Suite')),
        # 3. Multi-path: two parallel branches, each a two-actor sentence
        #    joined by a preposition.
        activity(
            path(organizer('Carol'), add('adds'), guest('Alice'), 'to', booking),
            path(organizer('Carol'), add('adds'), guest('Bob'), 'to', booking),
        ),
        # 4. Two work objects connected by a preposition.
        activity(
            organizer('Carol'), submit('submits'), payment, 'for', booking
        ),
        # 5. System confirms the booking.
        activity(booking_system, confirm('confirms'), booking),
        # 6. Multi-path send — one confirmation per guest, in parallel.
        activity(
            path(
                booking_system, send('sends'), confirmation, 'to', guest('Alice')
            ),
            path(booking_system, send('sends'), confirmation, 'to', guest('Bob')),
        ),
        # 7. Draft verb + draft work object — vocabulary the team hasn't yet
        #    committed; stays visibly uncovered until promoted to the glossary.
        activity(
            organizer('Carol'),
            draft.verb('redeems'),
            draft.work_object('loyalty points'),
        ),
    ],
)


@pytest.fixture
@given(t'our organizer {organizer("Carol")}')
def carol():
    return {'name': 'Carol', 'role': 'organizer'}


@pytest.fixture
@given(t'our guest {guest("Alice")}')
def alice():
    return {'name': 'Alice', 'email': 'alice@example.com'}


@pytest.fixture
@given(t'our guest {guest("Bob")}')
def bob():
    return {'name': 'Bob', 'email': 'bob@example.com'}


@scenario('Carol picks a suite for the group', story=book_a_group_trip)
def test_pick_suite(carol):
    with given(t'the {room("Deluxe Suite")} is listed as available'):
        catalog = {'Deluxe Suite': {'available': True}, 'Standard': {'available': False}}
    with when(t'{organizer("Carol")} {search("searches for")} a {room}'):
        offered = [name for name, r in catalog.items() if r['available']]
    with when(
        t'{organizer("Carol")} {select("selects")} the {room("Deluxe Suite")}'
    ):
        carol['selection'] = offered[0]
    with then(t'the {room("Deluxe Suite")} is held for {organizer("Carol")}'):
        assert carol['selection'] == 'Deluxe Suite'


@scenario('Carol completes the booking for both guests', story=book_a_group_trip)
def test_complete_booking(carol, alice, bob):
    with given(
        t'{organizer("Carol")} has {select("selected")} the {room("Deluxe Suite")}'
    ):
        booking_state = {
            'room': 'Deluxe Suite',
            'guests': [],
            'paid': False,
            'confirmed': False,
            'notified': [],
        }
    with when(
        t'{organizer("Carol")} {add("adds")} {guest("Alice")} '
        t'and {guest("Bob")} to the {booking}'
    ):
        booking_state['guests'] = [alice['name'], bob['name']]
    with when(
        t'{organizer("Carol")} {submit("submits")} the {payment} '
        t'for the {booking}'
    ):
        booking_state['paid'] = True
    with then(t'the {booking_system} {confirm("confirms")} the {booking}'):
        booking_state['confirmed'] = booking_state['paid']
        assert booking_state['confirmed']
    with then(
        t'the {booking_system} {send("sends")} the {confirmation} '
        t'to {guest("Alice")} and {guest("Bob")}'
    ):
        booking_state['notified'] = list(booking_state['guests'])
        assert set(booking_state['notified']) == {'Alice', 'Bob'}


SUPPORTED_PAYMENT_METHODS = {'credit card', 'debit card', 'bank transfer'}


@scenario(
    'Payment is declined — the booking is not finalized', story=book_a_group_trip
)
@pytest.mark.parametrize(
    'payment_method,decline_reason',
    [
        ('credit card', 'insufficient funds'),
        ('debit card', 'expired card'),
        ('bank transfer', 'fraud check failed'),
        # Gift cards aren't wired into the decline handler yet — this case
        # fails on the supported-method guard until the feature lands.
        ('gift card', 'partial balance'),
    ],
)
def test_payment_declined(carol, alice, bob, payment_method, decline_reason):
    with given(
        t'{organizer("Carol")} has {add("added")} {guest("Alice")} '
        t'and {guest("Bob")} to the {booking}'
    ):
        booking_state = {
            'guests': [alice['name'], bob['name']],
            'paid': False,
            'confirmed': False,
        }
    with when(
        t'{organizer("Carol")} {submit("submits")} the {payment} '
        t'by {payment_method} for the {booking}'
    ):
        # Payment processor reports the parameterized decline reason.
        processor_response = decline_reason
    with then(
        t'the {booking_system} {reject("rejects")} the {payment} '
        t'because of {decline_reason}'
    ):
        assert payment_method in SUPPORTED_PAYMENT_METHODS
        assert processor_response == decline_reason
        assert not booking_state['paid']
    with then(
        t'the {booking} stays pending and no {confirmation} is sent '
        t'to {guest("Alice")} or {guest("Bob")}'
    ):
        assert not booking_state['confirmed']
