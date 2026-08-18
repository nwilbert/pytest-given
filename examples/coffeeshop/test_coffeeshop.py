from typing import Annotated

import pytest

from pytest_given import Template, attach, given, scenario, then, when, when_then


@pytest.fixture
@given('a coffee machine')
def machine():
    return {'coffees': 10, 'price': 2}


@pytest.fixture
@given('a database connection')
def db():
    conn = {'open': True, 'queries': []}
    yield conn
    conn['open'] = False


@scenario(
    'Basic scenario with when/then and a JSON attachment',
    tags=['billing', 'happy-path'],
)
def test_buy_coffee(machine):
    with when('I insert $2'):
        machine['coffees'] -= 1
    with then('I get a coffee'):
        assert machine['coffees'] == 9
        attach('Machine state', machine)


@scenario('Plain text attachment', tags=['billing'])
def test_text_attachment(machine):
    with given('a printed receipt'):
        receipt = 'Coffee x1     $2.00\n----------------\nTotal:        $2.00'
        attach('Receipt', receipt)
    with when('the total line is read back'):
        total_line = receipt.splitlines()[-1]
    with then('it shows the $2.00 total'):
        assert total_line == 'Total:        $2.00'


@scenario('Generator fixture with teardown')
def test_generator_fixture(db):
    with when('I run a query'):
        db['queries'].append('SELECT 1')
    with then('the connection is open and the query was logged'):
        assert db['open']
        assert db['queries'] == ['SELECT 1']


@scenario(
    'Parametrized test (renders as a parameter table)',
    tags=['billing'],
)
@pytest.mark.parametrize(('euros', 'expect'), [(1, False), (2, True), (3, True)])
def test_pricing(machine, euros, expect):
    with when(t'I insert ${euros}'):
        purchase_allowed = euros >= machine['price']
    with then(t'the purchase is allowed: {expect}'):
        assert purchase_allowed == expect


@scenario(
    'Parametrize value surfaced as a given (Annotated)',
    tags=['billing'],
)
@pytest.mark.parametrize('cup_size', [200, 350])
def test_annotated_given_label(
    machine,
    cup_size: Annotated[int, given(Template('an order for a {cup_size} ml cup'))],
):
    with when('I brew the cup'):
        machine['coffees'] -= 1
    with then('the machine has one fewer coffee'):
        assert machine['coffees'] == 9


@scenario('T-string with a non-parametrize value (neutral highlight)')
def test_neutral_highlight(machine):
    with given('I have some coins in hand'):
        amount = 5
    with when(t'I insert ${amount}'):
        machine['credit'] = amount
        machine['coffees'] -= 1
    with then(t'the machine has {machine["coffees"]} coffees left'):
        assert machine['coffees'] == 9


@scenario(
    Template('Brew {cup_size} ml (templated scenario name)'),
    tags=['billing'],
)
@pytest.mark.parametrize('cup_size', [200, 300])
def test_brew(machine, cup_size):
    with when(t'I brew a {cup_size} ml cup'):
        machine['coffees'] -= 1
    with then('the machine has one fewer coffee'):
        assert machine['coffees'] < 10


@scenario(
    Template('Brew a {flavor} coffee (per-case columns)'),
    tags=['billing'],
)
@pytest.mark.parametrize('flavor', ['vanilla', 'mocha'])
def test_flavor_columns(machine, flavor):
    with given(t'the machine is primed for {flavor}'):
        attach('brew log', f'priming the {flavor} line\nheating to 93C\n')
    with when(t'I brew a {flavor} coffee'):
        price = machine['price'] + (1 if flavor == 'mocha' else 0)
        machine['coffees'] -= 1
    with then(t'the drink costs {price} euros'):
        assert price >= machine['price']


@when(Template('the coin is validated for ${amount}'))
def validate_coin_step(machine, amount):
    return amount >= machine['price']


@when(Template('the balance is updated'))
def update_balance_step(machine, valid):
    if valid:
        machine['coffees'] -= 1


def validate_coin(machine, amount):
    valid = validate_coin_step(machine, amount)
    update_balance_step(machine, valid)
    return valid


@scenario('Helper functions can record their own steps', tags=['billing'])
def test_buy_with_validation(machine):
    with when('I insert $2'):
        result = validate_coin(machine, 2)
    with then('the coin is accepted'):
        assert result is True
    with then('a coffee is dispensed'):
        assert machine['coffees'] == 9
        with then('the machine state is consistent'):
            assert machine['price'] == 2
            attach('Final state', machine)


@scenario('Top-level `given` block and deeply nested steps', tags=['billing'])
def test_complex_order(machine):
    with given('a loyalty card with 5 points'):
        loyalty = {'points': 5}
    with when('I place a large order'):
        with when('I select 3 coffees'):
            order_count = 3
        with when('I apply loyalty discount'):
            with when('the loyalty card is validated'):
                if loyalty['points'] <= 0:
                    raise ValueError('no loyalty points')
            with when('the discount is calculated'):
                discount = min(loyalty['points'], order_count)
                loyalty['points'] -= discount
    with then('the order is processed correctly'):
        with then('the coffee count is updated'):
            machine['coffees'] -= order_count
            assert machine['coffees'] == 7
        with then('the loyalty points are deducted'):
            assert loyalty['points'] == 2
            with then('the remaining points are valid'):
                assert loyalty['points'] >= 0
                attach('Loyalty state', loyalty)
    with then('the machine state is consistent'):
        assert machine['price'] == 2
        attach('Final machine state', machine)


def buy_coffee(machine):
    if machine['coffees'] <= 0:
        raise ValueError('the machine is sold out')
    machine['coffees'] -= 1


@scenario(
    'An expected error, narrated as when + then (when_then)',
    tags=['billing', 'validation'],
)
def test_sold_out_is_rejected(machine):
    with given('a machine that has sold its last coffee'):
        machine['coffees'] = 0
    with (
        when_then(
            'a customer tries to buy a coffee',
            'the machine reports it is sold out',
        ),
        pytest.raises(ValueError, match='sold out'),
    ):
        buy_coffee(machine)


@scenario(
    'Many tags (the report collapses them behind a +N pill)',
    tags=['billing', 'loyalty', 'discounts', 'happy-path', 'regression'],
)
def test_discounted_purchase(machine):
    with given('a loyalty card good for a $1 discount'):
        discount = 1
    with when('I buy a coffee with the discount'):
        price_paid = machine['price'] - discount
        machine['coffees'] -= 1
    with then('I pay $1'):
        assert price_paid == 1
    with then('a coffee is dispensed'):
        assert machine['coffees'] == 9


@scenario('Failure rendering (intentionally failing)')
def test_failing(machine):
    with then('the machine has 20 coffees'):
        assert machine['coffees'] == 20


@scenario('Skipped scenario rendering')
@pytest.mark.skip(reason='demonstrates skipped status')
def test_skipped(machine):
    with then('this step never runs'):
        assert machine['coffees'] == 10


@scenario('All cases skipped')
@pytest.mark.parametrize(
    'n',
    [
        pytest.param(1, marks=pytest.mark.skip(reason='awaiting fixture')),
        pytest.param(2, marks=pytest.mark.skip(reason='awaiting fixture')),
    ],
)
def test_parametrized_all_skipped(machine, n):
    with then('this case never runs'):
        assert machine['coffees'] == n
