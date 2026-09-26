"""Group hotel booking — showcases DDD glossary, Domain Story, and coverage.

An Organizer (Carol) reserves rooms for her colleagues Alice and Bob ahead of a
conference. The Story covers eight sentences exercising every part of the
domain-storytelling grammar: canonical entities, actor/work-object instances,
two work objects joined by a preposition, two actors in the same clause,
multi-clause sentences for parallel branches — one of them with clauses that
start at different actors — and a sentence whose vocabulary is undefined but
classified by kind inference.

The glossary holds only vocabulary with a meaning specific to the domain. The
verbs that are plain sentence prose — *searches for*, *selects*, *adds*,
*submits*, *sends*, *checks in to* — stay bare strings in the sentences; only
the activities a hotel would define (confirm, decline, cancel, refund) are
terms.

Three scenarios implement the Story at varying detail, each in full
Given/When/Then form:

* `test_pick_suite` — happy path, covers sentences 1-2. Both sentences
  narrate the same two terms (Organizer, Room) — their verbs are bare — so
  narration alone cannot tell them apart; the steps pin their sentence number
  with `activity=`.
* `test_complete_booking` — happy path through the rest, covers 2-6 and 8.
  Sentence 2 is intentionally shared with `test_pick_suite` so the Stories tab
  shows two badges on that row (its `given` pins sentence 2 for the same
  reason as above).
* `test_payment_declined` — parametrized error branch using a `decline` activity
  that lives in the glossary but isn't part of any story sentence. Cases pair
  a payment method with its decline reason (credit card / insufficient funds,
  debit card / expired card, bank transfer / fraud check), all funneling
  through the same decline path. Covers 3 and 4, overlapping with
  `test_complete_booking` to show how a scenario can probe a different aspect
  (the failure path) of the same sentences.

Sentence 7 uses `redeems` and `loyalty points`, both introduced with no kind
and no definition. The post-collection kind-inference pass classifies them
from their slot positions — `redeems` as an activity, `loyalty points` as a
work object — but both remain without a definition, so each renders with a kind
pill and an Undefined badge. No scenario currently references those terms,
so sentence 7 is an uncovered gap in the Stories view, signalling that the
vocabulary still needs to be exercised by a test.

A second, shorter Story — `Cancel a Booking` — shares the same glossary to
exercise the multi-story parts of the report (Stories tab, story filter) and to
show vocabulary reused across stories (Guest, Booking, Payment, Confirmation,
Booking System). Its single scenario `test_cancel_booking` covers all three of
its sentences.
"""

import pytest

from pytest_given import (
    Glossary,
    clause,
    given,
    scenario,
    sentence,
    story,
    then,
    when,
)

# Ubiquitous language for group bookings.
g = Glossary()

organizer = g.actor('Organizer', 'Person booking accommodation on behalf of a group.')
guest = g.actor('Guest', 'Individual traveler in the group.')
booking_system = g.actor('Booking System', 'Automated reservation back-end.')

room = g.work_object('Room', 'A bookable hotel room.')
booking = g.work_object('Booking', 'A reservation for one or more rooms.')
payment = g.work_object('Payment', 'Money transferred for a booking.')
confirmation = g.work_object('Confirmation', 'Notification of a successful booking.')

confirm = g.activity(
    'confirm', 'Guarantee a paid booking so its rooms are held for arrival.'
)
# `decline` is in the ubiquitous language but no Story sentence uses it yet —
# it surfaces in the Glossary tab and powers the error-path scenario.
decline = g.activity('decline', 'Refuse a payment, leaving its booking pending.')
# Vocabulary for the second Story.
cancel = g.activity('cancel', 'Withdraw a booking before arrival.')
refund = g.activity('refund', 'Return the payment for a cancelled booking.')


book_a_group_trip = story(
    'Book a Group Trip',
    [
        # 1. Actor instance + canonical work object (the room category, before
        #    any specific room is chosen).
        sentence(organizer('Carol'), 'searches for', room),
        # 2. Actor instance + work-object instance.
        sentence(organizer('Carol'), 'selects', room('Deluxe Suite')),
        # 3. Multi-clause: two parallel branches, each a two-actor clause
        #    joined by a preposition.
        sentence(
            clause(organizer('Carol'), 'adds', guest('Alice'), 'to', booking),
            clause(organizer('Carol'), 'adds', guest('Bob'), 'to', booking),
        ),
        # 4. Two work objects connected by a preposition.
        sentence(organizer('Carol'), 'submits', payment, 'for', booking),
        # 5. System confirms the booking.
        sentence(booking_system, confirm('confirms'), booking),
        # 6. Multi-clause send — one confirmation per guest, in parallel.
        sentence(
            clause(booking_system, 'sends', confirmation, 'to', guest('Alice')),
            clause(booking_system, 'sends', confirmation, 'to', guest('Bob')),
        ),
        # 7. Vocabulary the team hasn't classified yet — kindless until kind
        #    inference runs, and undefined until someone writes a definition.
        sentence(
            organizer('Carol'),
            g('redeems'),
            g('loyalty points'),
        ),
        # 8. Clauses that start at different actors: each guest checks in on
        #    their own, under one sentence number.
        sentence(
            clause(guest('Alice'), 'checks in to', room('Deluxe Suite')),
            clause(guest('Bob'), 'checks in to', room('Deluxe Suite')),
        ),
    ],
)


# A short second Story sharing the same glossary — exercises the multi-story
# parts of the report (Stories tab, story filter) and shows vocabulary reused
# across stories (Guest, Booking, Payment, Confirmation, Booking System).
cancel_a_booking = story(
    'Cancel a Booking',
    [
        # Guest instance withdraws a booking made on their behalf.
        sentence(guest('Alice'), cancel('cancels'), booking),
        # Two work objects joined by a preposition — the refund settles the
        # payment for that booking.
        sentence(booking_system, refund('refunds'), payment, 'for', booking),
        # Reuses the confirmation vocabulary from the first story.
        sentence(booking_system, 'sends', confirmation, 'to', guest('Alice')),
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
        catalog = {
            'Deluxe Suite': {'available': True},
            'Standard': {'available': False},
        }
    with when(t'{organizer("Carol")} searches for a {room}', activity=1):
        offered = [name for name, r in catalog.items() if r['available']]
    with when(t'{organizer("Carol")} selects the {room("Deluxe Suite")}', activity=2):
        carol['selection'] = offered[0]
    with then(t'the {room("Deluxe Suite")} is held for the group'):
        assert carol['selection'] == 'Deluxe Suite'


@scenario('Carol completes the booking for both guests', story=book_a_group_trip)
def test_complete_booking(carol, alice, bob):
    with given(
        t'{organizer("Carol")} has selected the {room("Deluxe Suite")}', activity=2
    ):
        booking_state = {
            'room': 'Deluxe Suite',
            'guests': [],
            'paid': False,
            'confirmed': False,
            'notified': [],
        }
    with when(
        t'{organizer("Carol")} adds {guest("Alice")} and {guest("Bob")} '
        t'to the {booking}'
    ):
        booking_state['guests'] = [alice['name'], bob['name']]
    with when(t'{organizer("Carol")} submits the {payment} for the {booking}'):
        booking_state['paid'] = True
    with then(t'the {booking_system} {confirm("confirms")} the {booking}'):
        booking_state['confirmed'] = booking_state['paid']
        assert booking_state['confirmed']
    with then(
        t'the {booking_system} sends the {confirmation} '
        t'to {guest("Alice")} and {guest("Bob")}'
    ):
        booking_state['notified'] = list(booking_state['guests'])
        assert set(booking_state['notified']) == {'Alice', 'Bob'}
    with when(
        t'{guest("Alice")} and {guest("Bob")} check in to the {room("Deluxe Suite")}'
    ):
        checked_in = [
            name
            for name in (alice['name'], bob['name'])
            if booking_state['confirmed'] and name in booking_state['guests']
        ]
    with then('both guests are checked in'):
        assert checked_in == ['Alice', 'Bob']


SUPPORTED_PAYMENT_METHODS = {'credit card', 'debit card', 'bank transfer'}


@scenario('Payment is declined — the booking is not finalized', story=book_a_group_trip)
@pytest.mark.parametrize(
    ('payment_method', 'decline_reason'),
    [
        ('credit card', 'insufficient funds'),
        ('debit card', 'expired card'),
        ('bank transfer', 'fraud check failed'),
        # Gift cards aren't wired into the payment processor yet — this case
        # fails until the feature lands.
        ('gift card', 'partial balance'),
    ],
)
def test_payment_declined(carol, alice, bob, payment_method, decline_reason):
    with given(
        t'{organizer("Carol")} has added {guest("Alice")} and {guest("Bob")} '
        t'to the {booking}'
    ):
        booking_state = {
            'guests': [alice['name'], bob['name']],
            'paid': False,
            'confirmed': False,
        }
    with when(
        t'{organizer("Carol")} submits the {payment} '
        t'by {payment_method} for the {booking}'
    ):
        # The processor declines a supported method for the parametrized
        # reason, and rejects an unsupported one outright.
        if payment_method in SUPPORTED_PAYMENT_METHODS:
            processor_response = decline_reason
        else:
            processor_response = 'unsupported payment method'
    with then(
        t'the {booking_system} {decline("declines")} the {payment} '
        t'because of {decline_reason}'
    ):
        assert processor_response == decline_reason
        assert not booking_state['paid']
    with then(
        t'the {booking} stays pending and no {confirmation} is sent '
        t'to {guest("Alice")} or {guest("Bob")}'
    ):
        assert not booking_state['confirmed']


@scenario('Alice cancels her booking and is refunded', story=cancel_a_booking)
def test_cancel_booking(alice):
    with given(t'{guest("Alice")} has a confirmed {booking} she paid for'):
        booking_state = {
            'guest': alice['name'],
            'paid': True,
            'cancelled': False,
            'refunded': False,
            'notified': [],
        }
    with when(t'{guest("Alice")} {cancel("cancels")} the {booking}'):
        booking_state['cancelled'] = True
    with then(
        t'the {booking_system} {refund("refunds")} the {payment} for the {booking}'
    ):
        booking_state['refunded'] = booking_state['cancelled'] and booking_state['paid']
        assert booking_state['refunded']
    with then(t'the {booking_system} sends a {confirmation} to {guest("Alice")}'):
        booking_state['notified'] = [alice['name']]
        assert booking_state['notified'] == ['Alice']
