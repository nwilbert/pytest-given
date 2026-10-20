from pytest_bdd import given, parsers, scenarios, then, when

scenarios('coffee.feature')


@given(
    parsers.parse('a coffee machine with {coffees:d} coffees'),
    target_fixture='machine',
)
def machine(coffees):
    return {'coffees': coffees, 'price': 2}


@when('I buy a coffee')
def buy_coffee(machine):
    machine['coffees'] -= 1


@then(parsers.parse('the machine has {coffees:d} coffees left'))
def coffees_left(machine, coffees):
    assert machine['coffees'] == coffees
