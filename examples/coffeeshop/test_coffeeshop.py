import pytest

from pytest_given import Template, attach, given, scenario, then, when


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


@scenario(
    'Parameterized test (renders as a parameter table)',
    tags=['billing'],
)
@pytest.mark.parametrize(('euros', 'expect'), [(1, False), (2, True), (3, True)])
def test_pricing(machine, euros, expect):
    with when(t'I insert ${euros}'):
        purchase_allowed = euros >= machine['price']
    with then(t'the purchase is allowed: {expect}'):
        assert purchase_allowed == expect


@scenario('T-string with a non-parametrize value (neutral highlight)')
def test_neutral_highlight(machine):
    with given('I have some coins in hand'):
        amount = 5
    with when(t'I insert ${amount}'):
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
                assert loyalty['points'] >= 3
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
