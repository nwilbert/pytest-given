"""Hotel stays, the *after* version of the example delta.

`examples/delta/before/` holds the same suite one release earlier. The `examples`
session stages each version under the same relative path, runs both and builds
the delta from the two reports. The changes between the versions are chosen so
the delta shows every surface it has. See `given-renames.toml` for the two
renames the delta cannot find by itself.
"""

import pytest

from pytest_given import Glossary, given, scenario, sentence, story, then, when

g = Glossary()

guest = g.actor('Guest', 'Person staying at the hotel.')
concierge = g.actor('Concierge', 'Staff member who arranges extras for guests.')

suite = g.work_object('Suite', 'A bookable hotel room.')
booking = g.work_object('Booking', 'A reservation for one room.')
invoice = g.work_object('Invoice', 'The itemised bill of a stay, settled at check-out.')
payment = g.work_object('Payment', 'Money transferred for a booking.')
upgrade = g.activity('upgrade', 'Move a guest to a better room at the same rate.')

# A story carries the glossary into the report. A suite without stories imports
# its glossary into a conftest.py instead.
hotel_stay = story('Stay at the hotel', [sentence(guest('Alice'), 'books', suite)])


@scenario('Guests check in with a digital key', tags=['front-desk', 'digital-key'])
def test_check_in():
    with given(t'{guest("Alice")} has a confirmed {booking}'):
        stay = {'guest': 'Alice', 'confirmed': True, 'key': None}
    with when(t'{guest("Alice")} gives her name at the front desk'):
        stay['arrived'] = True
    with then('the hotel sends her a digital key'):
        stay['key'] = 'digital key'
        assert stay['key'] == 'digital key'


@scenario('Cancelling a paid booking refunds it', tags=['cancellation'])
def test_cancel_booking():
    with given(t'{guest("Alice")} has a confirmed {booking} she paid for'):
        stay = {'status': 'confirmed', 'paid': True}
    with when(t'{guest("Alice")} cancels the {booking}'):
        stay['status'] = 'cancelled'
    with then(t'the hotel returns the {payment} in full'):
        stay['refunded'] = stay['paid']
        assert stay['refunded']
    with then(t'the cancellation is noted on the {invoice}'):
        stay['invoice_note'] = 'cancelled'
        assert stay['invoice_note']


@scenario('A walk-in guest is offered the next free suite', tags=['front-desk'])
def test_walk_in_booking():
    with given(t'the front desk has one free {suite}'):
        free_rooms = ['101']
    with when(t'a walk-in {guest("Bob")} asks for a {suite}'):
        assigned = free_rooms.pop()
    with then(t'{guest("Bob")} gets {suite("Suite 101")}'):
        assert assigned == '101'


@scenario('Returning guests get a loyalty discount on the invoice')
def test_loyalty_discount():
    with given(t'{guest("Alice")} has stayed three times before'):
        previous_stays = 3
    with when(t'the {concierge} prepares her {invoice}'):
        discount = 10 if previous_stays >= 3 else 0
    with then('the total is reduced by 10 percent'):
        assert discount == 10


@scenario('A quote names the nightly rate of a room')
def test_quote_rate():
    with given(t'a free {suite}'):
        nightly_rate = 90
    with when(t'{guest("Alice")} asks for a quote'):
        quote = {'rate': nightly_rate, 'nights': 2}
    with then(t'the quote shows the total and offers an {upgrade}'):
        assert quote['rate'] * quote['nights'] == 180


def submit_payment(method, amount, reason):
    if method == 'gift card':
        raise NotImplementedError('gift cards are not wired into payments yet')
    return reason if amount else None


@scenario('A declined payment leaves the booking pending', tags=['error-handling'])
@pytest.mark.parametrize(
    ('payment_method', 'reason', 'amount'),
    [
        pytest.param('credit card', 'insufficient funds', 120, id='credit-card'),
        pytest.param('debit card', 'expired card', 95, id='debit-card'),
        pytest.param('gift card', 'partial balance', 50, id='gift-card'),
        pytest.param('voucher', 'voucher expired', 40, id='voucher'),
    ],
)
def test_payment_declined(payment_method, reason, amount):
    fee = amount // 10
    with given(t'{guest("Alice")} has a pending {booking}'):
        pending = {'paid': False}
    with when(
        t'{guest("Alice")} submits the {payment} by {payment_method} '
        t'with a fee of {fee}'
    ):
        response = submit_payment(payment_method, amount, reason)
    with then(t'the hotel declines the {payment} because of {reason}'):
        assert response == reason
    with then(t'the {booking} stays pending'):
        assert not pending['paid']
