"""Hotel stays, the *before* version of the example delta.

`examples/delta/after/` holds the same suite one release later. The `examples`
session stages each version under the same relative path, runs both and builds
the delta from the two reports. The changes between the versions are chosen so
the delta shows every surface it has. See `given-renames.toml` for the two
renames the delta cannot find by itself.
"""

import pytest

from pytest_given import Glossary, given, scenario, sentence, story, then, when

g = Glossary()

guest = g.actor('Guest', 'Person staying at the hotel.')
receptionist = g.actor('Receptionist', 'Staff member who works the front desk.')

room = g.work_object('Room', 'A bookable hotel room.')
booking = g.work_object('Booking', 'A reservation for one room.')
invoice = g.work_object('Invoice', 'A bill for a stay.')
payment = g.work_object('Payment', 'Money transferred for a booking.')
upgrade = g.work_object('Upgrade', 'A better room offered at the same rate.')

# A story carries the glossary into the report. A suite without stories imports
# its glossary into a conftest.py instead.
hotel_stay = story('Stay at the hotel', [sentence(guest('Alice'), 'books', room)])


@scenario('Guests check in at the front desk', tags=['front-desk'])
def test_check_in():
    with given(t'{guest("Alice")} has a confirmed {booking}'):
        stay = {'guest': 'Alice', 'confirmed': True, 'key': None}
    with when(t'{guest("Alice")} gives her name at the front desk'):
        stay['arrived'] = True
    with then('the hotel hands her a key card'):
        stay['key'] = 'key card'
        assert stay['key'] == 'key card'


@scenario('Cancelling a paid booking refunds it', tags=['cancellation', 'legacy'])
def test_cancel_booking():
    with given(t'{guest("Alice")} has a confirmed {booking} she paid for'):
        stay = {'status': 'confirmed', 'paid': True}
    with when(t'{guest("Alice")} cancels the {booking}'):
        stay['status'] = 'cancelled'
    with then(t'the hotel returns the {payment} in full'):
        stay['refunded'] = stay['paid']
        assert stay['refunded']
    with then(t'{guest("Alice")} receives a cancellation email with her {invoice}'):
        stay['notified'] = True
        assert stay['notified']


@scenario('A walk-in guest gets the next free room', tags=['front-desk'])
def test_walk_in():
    with given(t'{receptionist("Dana")} has one free {room}'):
        free_rooms = ['101']
    with when(t'a walk-in {guest("Bob")} asks for a {room}'):
        assigned = free_rooms.pop()
    with then(t'{guest("Bob")} gets {room("Room 101")}'):
        assert assigned == '101'


@scenario('Late check-out is refused when the next guest arrives early')
def test_late_checkout():
    with given(t'the next {guest("Carol")} arrives at noon'):
        next_arrival = 12
    with when(t'{guest("Alice")} asks the {receptionist} for a 2 pm check-out'):
        allowed = next_arrival > 14
    with then('the request is refused'):
        assert not allowed


@scenario('A quote names the nightly rate of a room')
def test_quote_rate():
    with given(t'a free {room}'):
        nightly_rate = 90
    with when(t'{guest("Alice")} asks for a quote'):
        quote = {'rate': nightly_rate, 'nights': 2}
    with then(t'the quote shows the total and offers an {upgrade}'):
        assert quote['rate'] * quote['nights'] == 180


def submit_payment(method, amount, decline_reason):
    if method == 'gift card':
        raise NotImplementedError('gift cards are not wired into payments yet')
    return decline_reason if amount else None


@scenario('A declined payment leaves the booking pending', tags=['error-handling'])
@pytest.mark.parametrize(
    ('payment_method', 'decline_reason', 'amount'),
    [
        pytest.param('credit card', 'insufficient funds', 120, id='credit-card'),
        pytest.param('debit card', 'expired card', 80, id='debit-card'),
        pytest.param('bank transfer', 'fraud check failed', 300, id='bank-transfer'),
        pytest.param(
            'gift card',
            'partial balance',
            50,
            id='gift-card',
            marks=pytest.mark.xfail(reason='gift cards are not wired in yet'),
        ),
    ],
)
def test_payment_declined(payment_method, decline_reason, amount):
    with given(t'{guest("Alice")} has a pending {booking}'):
        pending = {'paid': False}
    with when(t'{guest("Alice")} submits the {payment} by {payment_method}'):
        response = submit_payment(payment_method, amount, decline_reason)
    with then(t'the hotel declines the {payment} because of {decline_reason}'):
        assert response == decline_reason
    with then(t'the {booking} stays pending'):
        assert not pending['paid']
