import pytest

from pytest_given import attach, given, scenario, then, when


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
    with when('I print the receipt'):
        receipt = 'Coffee x1     $2.00\n----------------\nTotal:        $2.00'
    with then('the receipt is recorded verbatim'):
        attach('Receipt', receipt)


@scenario('Generator fixture with teardown')
def test_generator_fixture(db):
    with when('I run a query'):
        db['queries'].append('SELECT 1')
    with then('the connection is open and the query was logged'):
        assert db['open']
        assert db['queries'] == ['SELECT 1']


@scenario('Not enough money', tags=['billing', 'edge-case'])
def test_not_enough(machine):
    with when('I insert $1'):
        paid = 1
    with then("I don't get a coffee"):
        assert paid < machine['price']


@scenario(
    'Parameterized test (renders as a parameter table)',
    tags=['billing'],
)
@pytest.mark.parametrize('euros,expect', [(1, False), (2, True), (3, True)])
def test_pricing(machine, euros, expect):
    with when(f'I insert ${euros}'):
        can_buy = euros >= machine['price']
    with then(f'can_buy is {expect}'):
        assert can_buy == expect


def validate_coin(machine, amount):
    with when(f'validating coin... {"accepted" if amount >= machine["price"] else "rejected"}'):
        valid = amount >= machine['price']
    with when('updating balance'):
        if valid:
            machine['coffees'] -= 1
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
            with when('validating loyalty card'):
                assert loyalty['points'] >= 3
            with when('calculating discount'):
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


@scenario('Failure rendering (intentionally failing)')
def test_failing(machine):
    with then('the machine has 20 coffees'):
        assert machine['coffees'] == 20
