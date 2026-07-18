# pytest-given — pytest-given

## ✓ Basic scenario with when/then and a JSON attachment
`examples/coffeeshop/test_coffeeshop.py:22::test_buy_coffee` · billing, happy-path

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
`examples/coffeeshop/test_coffeeshop.py:34::test_text_attachment` · billing

- **given** a coffee machine
- **given** a printed receipt
  - 📎 Receipt:
    ```
    Coffee x1     $2.00
    ----------------
    Total:        $2.00
    ```
- **when** the total line is read back
- **then** it shows the $2.00 total

## ✓ Generator fixture with teardown
`examples/coffeeshop/test_coffeeshop.py:45::test_generator_fixture`

- **given** a database connection
- **when** I run a query
- **then** the connection is open and the query was logged

## ✓ T-string with a non-parametrize value (neutral highlight)
`examples/coffeeshop/test_coffeeshop.py:81::test_neutral_highlight`

- **given** a coffee machine
- **given** I have some coins in hand
- **when** I insert $5
- **then** the machine has 9 coffees left

## ✓ Helper functions can record their own steps
`examples/coffeeshop/test_coffeeshop.py:121::test_buy_with_validation` · billing

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
`examples/coffeeshop/test_coffeeshop.py:134::test_complex_order` · billing

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
`examples/coffeeshop/test_coffeeshop.py:168::test_sold_out_is_rejected` · billing, validation

- **given** a coffee machine
- **given** a machine that has sold its last coffee
- **when** a customer tries to buy a coffee
- **then** the machine reports it is sold out

## ✓ Many tags (the report collapses them behind a +N pill)
`examples/coffeeshop/test_coffeeshop.py:185::test_discounted_purchase` · billing, loyalty, discounts, happy-path, regression

- **given** a coffee machine
- **given** a loyalty card good for a $1 discount
- **when** I buy a coffee with the discount
- **then** I pay $1
- **then** a coffee is dispensed

## ✗ Failure rendering (intentionally failing)
`examples/coffeeshop/test_coffeeshop.py:201::test_failing`

- **given** a coffee machine
- **then** the machine has 20 coffees

## ⤼ Skipped scenario rendering · skipped
`examples/coffeeshop/test_coffeeshop.py:207::test_skipped` — reason: demonstrates skipped status


## ✓ Parametrized test (renders as a parameter table) · 3 cases
`examples/coffeeshop/test_coffeeshop.py:54::test_pricing` · billing

- **given** a coffee machine
- **when** I insert ${euros}
- **then** the purchase is allowed: {expect}

| euros | expect | |
|---|---|---|
| 1 | False | ✓ |
| 2 | True | ✓ |
| 3 | True | ✓ |

## ✓ Parametrize value surfaced as a given (Annotated) · 2 cases
`examples/coffeeshop/test_coffeeshop.py:66::test_annotated_given_label` · billing

- **given** a coffee machine
- **given** an order for a {cup_size} ml cup
- **when** I brew the cup
- **then** the machine has one fewer coffee

| cup_size | |
|---|---|
| 200 | ✓ |
| 350 | ✓ |

## ✓ Brew {cup_size} ml (templated scenario name) · 2 cases
`examples/coffeeshop/test_coffeeshop.py:92::test_brew` · billing

- **given** a coffee machine
- **when** I brew a {cup_size} ml cup
- **then** the machine has one fewer coffee

| cup_size | |
|---|---|
| 200 | ✓ |
| 300 | ✓ |

## ⤼ All cases skipped · skipped
`examples/coffeeshop/test_coffeeshop.py:214::test_parametrized_all_skipped`


| n | |
|---|---|
| 1 | ⤼ |
| 2 | ⤼ |
