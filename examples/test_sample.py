import pytest

from pytest_given import attach, given, scenario, then, when


@pytest.fixture
@given('a coffee machine')
def machine():
    return {'coffees': 10, 'price': 2}


@scenario('Buy coffee', tags=['billing', 'happy-path'])
def test_buy_coffee(machine):
    with when('I insert $2'):
        machine['coffees'] -= 1
    with then('I get a coffee'):
        assert machine['coffees'] == 9
        attach('Machine state', str(machine))


@scenario('Not enough money', tags=['billing', 'edge-case'])
def test_not_enough(machine):
    with when('I insert $1'):
        paid = 1
    with then("I don't get a coffee"):
        assert paid < machine['price']


@scenario('Pricing', tags=['billing'])
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


@scenario('Buy coffee with validation', tags=['billing', 'detailed'])
def test_buy_with_validation(machine):
    with when('I insert $2'):
        result = validate_coin(machine, 2)
    with then('the coin is accepted'):
        assert result is True
    with then('a coffee is dispensed'):
        assert machine['coffees'] == 9
        with then('the machine state is consistent'):
            assert machine['price'] == 2
            attach('Final state', str(machine))


@scenario('Complex ordering workflow', tags=['billing', 'detailed'])
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
                attach('Loyalty state', str(loyalty))
    with then('the machine state is consistent'):
        assert machine['price'] == 2
        attach('Final machine state', str(machine))


@scenario('Failing assertion', tags=['debug'])
def test_failing(machine):
    with then('the machine has 20 coffees'):
        assert machine['coffees'] == 20
