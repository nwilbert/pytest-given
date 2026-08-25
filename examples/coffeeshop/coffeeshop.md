# pytest-given — Coffee Shop Example

## ✓ Basic scenario with when/then and a JSON attachment
`examples/coffeeshop/test_coffeeshop.py:22::test_buy_coffee` · checkout

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
`examples/coffeeshop/test_coffeeshop.py:34::test_text_attachment`

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
`examples/coffeeshop/test_coffeeshop.py:78::test_neutral_highlight`

- **given** a coffee machine
- **given** I have some coins in hand
- **when** I insert $5
- **then** the machine has 9 coffees left

## ✓ Helper functions can record their own steps
`examples/coffeeshop/test_coffeeshop.py:162::test_buy_with_validation` · checkout, validation

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
`examples/coffeeshop/test_coffeeshop.py:178::test_complex_order` · checkout, loyalty, discounts

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
`examples/coffeeshop/test_coffeeshop.py:215::test_sold_out_is_rejected` · checkout, validation

- **given** a coffee machine
- **given** a machine that has sold its last coffee
- **when** a customer tries to buy a coffee
- **then** the machine reports it is sold out

## ✓ Many tags (the report collapses them behind a +N pill)
`examples/coffeeshop/test_coffeeshop.py:232::test_discounted_purchase` · checkout, loyalty, discounts, pricing, inventory

- **given** a coffee machine
- **given** a loyalty card good for a $1 discount
- **when** I buy a coffee with the discount
- **then** I pay $1
- **then** a coffee is dispensed

## ✗ Failure rendering (intentionally failing)
`examples/coffeeshop/test_coffeeshop.py:248::test_failing`

- **given** a coffee machine
- **then** the machine has 20 coffees

> assert 10 == 20
> test_coffeeshop.py:251 in test_failing

## ⤼ Skipped scenario rendering · skipped
`examples/coffeeshop/test_coffeeshop.py:254::test_skipped` — reason: demonstrates skipped status


## ✓ Parametrized test (renders as a parameter table) · 3 cases
`examples/coffeeshop/test_coffeeshop.py:54::test_pricing` · pricing

- **given** a coffee machine
- **when** I insert ${euros}
- **then** the purchase is allowed: {expect}

| euros | expect | |
|---|---|---|
| 1 | False | ✓ |
| 2 | True | ✓ |
| 3 | True | ✓ |

## ✓ Parametrize value surfaced as a given (Annotated) · 2 cases
`examples/coffeeshop/test_coffeeshop.py:66::test_annotated_given_label`

- **given** a coffee machine
- **given** an order for a {cup_size} ml cup
- **when** I brew the cup
- **then** the machine has one fewer coffee

| cup_size | |
|---|---|
| 200 | ✓ |
| 350 | ✓ |

## ✓ Brew {cup_size} ml (templated scenario name) · 2 cases
`examples/coffeeshop/test_coffeeshop.py:89::test_brew`

- **given** a coffee machine
- **when** I brew a {cup_size} ml cup
- **then** the machine has one fewer coffee

| cup_size | |
|---|---|
| 200 | ✓ |
| 300 | ✓ |

## ✓ Serve a 200 ml cup (one scenario per case) [200]
`examples/coffeeshop/test_coffeeshop.py:98::test_serve`

- **given** a coffee machine
- **when** I order a 200 ml cup
- **then** the machine has one fewer coffee

## ✓ Serve a 400 ml cup (one scenario per case) [400]
`examples/coffeeshop/test_coffeeshop.py:98::test_serve`

- **given** a coffee machine
- **given** the barista reaches for a takeaway cup
- **when** I order a 400 ml cup
- **then** the machine has one fewer coffee

## ✓ Brew a {flavor} coffee (per-case columns) · 2 cases
`examples/coffeeshop/test_coffeeshop.py:115::test_flavor_columns` · pricing

- **given** a coffee machine
- **given** the machine is primed for {flavor}
  - 📎 brew log — *see parameter table*
- **when** I brew a {flavor} coffee
- **then** the drink costs {price} euros

| flavor | brew log | price | |
|---|---|---|---|
| vanilla | brew log | 2 | ✓ |
| mocha | brew log | 3 | ✓ |

- **vanilla** — brew log:
  ```
  00:00  purge vanilla line, 40 ml at 92.8C
  00:04  dose 18.5 g, grind 12, hopper: vanilla
  00:09  pre-infuse at 3.0 bar for 4.0 s
  00:13  ramp to 9.0 bar
  00:27  stop at 36.0 g yield, ratio 1:1.95
  00:31  purge group head, vanilla residue cleared
  ```

- **mocha** — brew log:
  ```
  00:00  purge mocha line, 40 ml at 92.8C
  00:04  dose 18.5 g, grind 12, hopper: mocha
  00:09  pre-infuse at 3.0 bar for 4.0 s
  00:13  ramp to 9.0 bar
  00:27  stop at 36.0 g yield, ratio 1:1.95
  00:31  purge group head, mocha residue cleared
  ```

## ⤼ All cases skipped · skipped
`examples/coffeeshop/test_coffeeshop.py:261::test_parametrized_all_skipped`


| n | |
|---|---|
| 1 | ⤼ |
| 2 | ⤼ |
