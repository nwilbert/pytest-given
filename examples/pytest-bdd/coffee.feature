Feature: Coffee machine

  @checkout
  Scenario: Buying a coffee takes one from the machine
    Given a coffee machine with 10 coffees
    When I buy a coffee
    Then the machine has 9 coffees left
