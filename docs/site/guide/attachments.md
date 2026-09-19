# Attachments

## `attach(label, content)`

Attach data to the current step. Strings are stored verbatim; other types are JSON-serialized.

```python
attach('Receipt', 'Coffee x1     $2.00')             # text
attach('Machine state', {'coffees': 9, 'price': 2})  # JSON
```

An attachment binds to the step being recorded, so the call belongs inside a `given` / `when` / `then` block — attaching from the test body with no step open raises.

The label is a plain `str`; a `Template` or t-string label raises — build it with an f-string if it needs interpolating.

In a parametrized scenario the label must read the same in every case; a payload that varies becomes a parameter-table column headed by that label, with a badge on the step pointing at it (see [Parametrized scenarios](parametrized.md)).

