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
the activities a hotel would define (confirm, decline, cancel, refund, rebook) are
terms.

Four scenarios bind to the Story. Three implement it at varying detail, each
in full Given/When/Then form; the fourth, `test_check_in_then_cancel`, binds a
second story too and is described below:

* `test_pick_suite` — happy path, covers sentences 1-2. Both sentences
  narrate the same two terms (Organizer, Room) — their verbs are bare — so
  narration alone cannot tell them apart; the steps pin them by name with
  `pins=book_a_group_trip['search']` and `['select']`.
* `test_complete_booking` — happy path through the rest, covers 2-6 and 8.
  Sentence 2 is intentionally shared with `test_pick_suite` so the Stories tab
  shows two badges on that row (its `given` pins `'select'` for the same
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
Booking System). `test_cancel_booking` covers its first three sentences. The
fourth, rebooking, is a planned feature: `test_rebook_cancelled_booking` pins it
and is marked `xfail(strict=True)`, so the Stories tab reads that sentence as
expected to fail rather than as broken or uncovered.
`test_check_in_then_cancel` binds both stories with `stories=`: Alice checks in
to the Deluxe Suite (sentence 8 of the first story), then cancels a later
booking (the `'cancel'` sentence of the second), so the Stories tab lists it
under each; the stay she has checked in to can no longer be cancelled.

The two scenarios that end in a refusal carry an `error-handling` tag, and
`test_payment_declined` a `ticket/HB-17` tag for the unwired gift card, so the
Stories tab shows tagged scenarios too.
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
    when_then,
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
rebook = g.activity(
    'rebook', 'Restore a cancelled booking for the same rooms and dates.'
)


book_a_group_trip = story(
    'Book a Group Trip',
    [
        # 1. Actor instance + canonical work object (the room category, before
        #    any specific room is chosen).
        sentence(organizer('Carol'), 'searches for', room, name='search'),
        # 2. Actor instance + work-object instance.
        sentence(organizer('Carol'), 'selects', room('Deluxe Suite'), name='select'),
        # 3. Multi-clause: two parallel branches, each a two-actor clause
        #    joined by a preposition.
        sentence(
            clause(organizer('Carol'), 'adds', guest('Alice'), 'to', booking),
            clause(organizer('Carol'), 'adds', guest('Bob'), 'to', booking),
        ),
        # 4. Two work objects connected by a preposition.
        sentence(organizer('Carol'), 'submits', payment, 'for', booking),
        # 5. System confirms the booking.
        sentence(booking_system, confirm.s, booking),
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
        sentence(guest('Alice'), cancel.s, booking, name='cancel'),
        # Two work objects joined by a preposition — the refund settles the
        # payment for that booking.
        sentence(booking_system, refund.s, payment, 'for', booking),
        # Reuses the confirmation vocabulary from the first story.
        sentence(booking_system, 'sends', confirmation, 'to', guest('Alice')),
        # The planned feature the xfail scenario demonstrates; "asks to rebook"
        # shows a multi-word inflection under the activity's "Also used as".
        sentence(guest('Alice'), rebook('asks to rebook'), booking, name='rebook'),
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


SUPPORTED_PAYMENT_METHODS = {'credit card', 'debit card', 'bank transfer'}


def submit_payment(booking, method, decline_reason=None):
    """Confirm the booking and notify its guests, unless the payment is declined.

    `decline_reason` stands in for the payment processor's answer.
    """
    if method not in SUPPORTED_PAYMENT_METHODS:
        return 'unsupported payment method'
    if decline_reason:
        return decline_reason
    booking['paid'] = booking['confirmed'] = True
    booking['notified'] = list(booking['guests'])
    return None


@scenario('A search offers only the available rooms', stories=book_a_group_trip)
def test_pick_suite(carol):
    with given(t'the {room("Deluxe Suite")} is listed as available'):
        catalog = {
            'Deluxe Suite': {'available': True},
            'Standard': {'available': False},
        }
    with when(
        t'{organizer("Carol")} searches for a {room}', pins=book_a_group_trip['search']
    ):
        offered = [name for name, r in catalog.items() if r['available']]
    with then(t'only the {room("Deluxe Suite")} is offered'):
        assert offered == ['Deluxe Suite']
    with when(
        t'{organizer("Carol")} selects the {room("Deluxe Suite")}',
        pins=book_a_group_trip['select'],
    ):
        carol['selection'] = offered[0]
    with then(t'the {room("Deluxe Suite")} is selected for the group'):
        assert carol['selection'] == 'Deluxe Suite'


@scenario('A paid booking is confirmed to every guest', stories=book_a_group_trip)
def test_complete_booking(carol, alice, bob):
    with given(
        t'{organizer("Carol")} has selected the {room("Deluxe Suite")}',
        pins=book_a_group_trip['select'],
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
        submit_payment(booking_state, 'credit card')
    with then(t'the {booking_system} {confirm.s} the {booking}'):
        assert booking_state['confirmed']
    with then(
        t'the {booking_system} sends the {confirmation} '
        t'to {guest("Alice")} and {guest("Bob")}'
    ):
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


@scenario(
    'A declined payment leaves the booking pending',
    stories=book_a_group_trip,
    tags=['error-handling', 'ticket/HB-17'],
)
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
            'notified': [],
        }
    with when(
        t'{organizer("Carol")} submits the {payment} '
        t'by {payment_method} for the {booking}'
    ):
        response = submit_payment(booking_state, payment_method, decline_reason)
    with then(
        t'the {booking_system} {decline.s} the {payment} because of {decline_reason}'
    ):
        assert response == decline_reason
        assert not booking_state['paid']
    with then(
        t'the {booking} stays pending and no {confirmation} is sent '
        t'to {guest("Alice")} or {guest("Bob")}'
    ):
        assert not booking_state['confirmed']
        assert booking_state['notified'] == []


def cancel_before_arrival(stay):
    if stay['status'] == 'checked in':
        raise ValueError('cannot cancel a booking after arrival')
    stay['status'] = 'cancelled'
    if stay.get('paid'):
        stay['refunded'] = True
        stay['notified'] = [stay['guest']]


@scenario(
    'Cancelling a paid booking refunds it and notifies the guest',
    stories=cancel_a_booking,
)
def test_cancel_booking(alice):
    with given(t'{guest("Alice")} has a confirmed {booking} she paid for'):
        stay = {'guest': alice['name'], 'status': 'confirmed', 'paid': True}
    with when(t'{guest("Alice")} {cancel.s} the {booking}'):
        cancel_before_arrival(stay)
    with then(t'the {booking_system} {refund.s} the {payment} for the {booking}'):
        assert stay['refunded']
    with then(t'the {booking_system} sends a {confirmation} to {guest("Alice")}'):
        assert stay['notified'] == ['Alice']


def rebook_cancelled_booking(stay):
    raise NotImplementedError('rebooking a cancelled booking is not supported yet')


@scenario('Rebooking restores a cancelled booking', stories=cancel_a_booking)
@pytest.mark.xfail(strict=True, reason='rebooking is not implemented yet')
def test_rebook_cancelled_booking(alice):
    with given(t'{guest("Alice")} has cancelled her stay'):
        stay = {'guest': alice['name'], 'status': 'cancelled'}
    with when(
        t'{guest("Alice")} {rebook.s} the {booking}',
        pins=cancel_a_booking['rebook'],
    ):
        rebook_cancelled_booking(stay)
    with then(t'the {booking} is confirmed again'):
        assert stay['status'] == 'confirmed'


def check_in(stay):
    if stay['status'] != 'confirmed':
        raise ValueError(f'cannot check in to a {stay["status"]} booking')
    stay['status'] = 'checked in'


@scenario(
    'A booking can be cancelled only before its guest checks in',
    stories=[cancel_a_booking, book_a_group_trip],
    tags=['error-handling'],
)
def test_check_in_then_cancel(alice):
    with given(t'{guest("Alice")} has a confirmed {booking} now and one next month'):
        current_stay = {
            'guest': alice['name'],
            'room': 'Deluxe Suite',
            'status': 'confirmed',
        }
        later_stay = {
            'guest': alice['name'],
            'room': 'Deluxe Suite',
            'status': 'confirmed',
        }
    with when(t'{guest("Alice")} checks in to the {room("Deluxe Suite")}'):
        check_in(current_stay)
    with then('her current stay is checked in'):
        assert current_stay['status'] == 'checked in'
    with when(t'{guest("Alice")} {cancel.s} her later {booking}'):
        cancel_before_arrival(later_stay)
    with then('the later booking is cancelled'):
        assert later_stay['status'] == 'cancelled'
    with (
        when_then(
            'she tries to cancel the stay she has checked in to',
            'the cancellation is refused',
        ),
        pytest.raises(ValueError, match='after arrival'),
    ):
        cancel_before_arrival(current_stay)
