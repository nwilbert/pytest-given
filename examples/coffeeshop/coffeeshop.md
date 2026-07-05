# pytest-given — pytest-given

## ✓ Basic scenario with when/then and a JSON attachment
`examples/coffeeshop/test_coffeeshop.py::test_buy_coffee` · billing, happy-path

- **given** a coffee machine
- **when** I insert $2
- **then** I get a coffee
  - 📎 Machine state:
    ```
    {
      "coffees": 9,
      "price": 2
    }
    ```

## ✓ Plain text attachment
`examples/coffeeshop/test_coffeeshop.py::test_text_attachment` · billing

- **given** a coffee machine
- **when** I print the receipt
- **then** the receipt is recorded verbatim
  - 📎 Receipt:
    ```
    Coffee x1     $2.00
    ----------------
    Total:        $2.00
    ```

## ✓ Generator fixture with teardown
`examples/coffeeshop/test_coffeeshop.py::test_generator_fixture`

- **given** a database connection
- **when** I run a query
- **then** the connection is open and the query was logged

## ✓ T-string with a non-parametrize value (neutral highlight)
`examples/coffeeshop/test_coffeeshop.py::test_neutral_highlight`

- **given** a coffee machine
- **given** I have some coins in hand
- **when** I insert $5
- **then** the machine has 9 coffees left

## ✓ Helper functions can record their own steps
`examples/coffeeshop/test_coffeeshop.py::test_buy_with_validation` · billing

- **given** a coffee machine
- **when** I insert $2
  - **when** the coin is validated for $2
  - **when** the balance is updated
- **then** the coin is accepted
- **then** a coffee is dispensed
  - **then** the machine state is consistent
    - 📎 Final state:
      ```
      {
        "coffees": 9,
        "price": 2
      }
      ```

## ✓ Top-level `given` block and deeply nested steps
`examples/coffeeshop/test_coffeeshop.py::test_complex_order` · billing

- **given** a coffee machine
- **given** a loyalty card with 5 points
- **when** I place a large order
  - **when** I select 3 coffees
  - **when** I apply loyalty discount
    - **when** the loyalty card is validated
    - **when** the discount is calculated
- **then** the order is processed correctly
  - **then** the coffee count is updated
  - **then** the loyalty points are deducted
    - **then** the remaining points are valid
      - 📎 Loyalty state:
        ```
        {
          "points": 2
        }
        ```
- **then** the machine state is consistent
  - 📎 Final machine state:
    ```
    {
      "coffees": 7,
      "price": 2
    }
    ```

## ✓ An expected error, narrated as when + then (when_then)
`examples/coffeeshop/test_coffeeshop.py::test_sold_out_is_rejected` · billing, validation

- **given** a coffee machine
- **given** a machine that has sold its last coffee
- **when** a customer tries to buy a coffee
- **then** the machine reports it is sold out

## ✗ Failure rendering (intentionally failing)
`examples/coffeeshop/test_coffeeshop.py::test_failing`

- **given** a coffee machine
- **then** the machine has 20 coffees

## ⤼ Skipped scenario rendering · skipped
`examples/coffeeshop/test_coffeeshop.py::test_skipped` — reason: demonstrates skipped status


## ✓ Parameterized test (renders as a parameter table) · 3 cases
`examples/coffeeshop/test_coffeeshop.py::test_pricing[1-False]` · billing

- **given** a coffee machine
- **when** I insert ${euros}
- **then** the purchase is allowed: {expect}

| euros | expect | |
|---|---|---|
| 1 | False | ✓ |
| 2 | True | ✓ |
| 3 | True | ✓ |

## ✓ Parametrize value surfaced as a given (Annotated) · 2 cases
`examples/coffeeshop/test_coffeeshop.py::test_annotated_given_label[200]` · billing

- **given** a coffee machine
- **given** an order for a {cup_size} ml cup
- **when** I brew the cup
- **then** the machine has one fewer coffee

| cup_size | |
|---|---|
| 200 | ✓ |
| 350 | ✓ |

## ✓ Brew {cup_size} ml (templated scenario name) · 2 cases
`examples/coffeeshop/test_coffeeshop.py::test_brew[200]` · billing

- **given** a coffee machine
- **when** I brew a {cup_size} ml cup
- **then** the machine has one fewer coffee

| cup_size | |
|---|---|
| 200 | ✓ |
| 300 | ✓ |

## ⤼ All cases skipped · skipped
`examples/coffeeshop/test_coffeeshop.py::test_parametrized_all_skipped[1]`


| n | |
|---|---|
| 1 | ⤼ |
| 2 | ⤼ |
