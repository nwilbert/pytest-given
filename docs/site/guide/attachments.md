# Attachments

`attach(label, content)`

Attach data to the current step. Strings are stored as they are; other values are stored as JSON.

```python
attach('Receipt', 'Coffee x1     $2.00')             # text
attach('Machine state', {'coffees': 9, 'price': 2})  # JSON
```

An attachment belongs to the current step, so call `attach` inside a `given`, `when` or `then` block. Calling it outside a step raises an error.

The label must be a plain string; a `Template` or t-string raises an error. Use an f-string if the label needs a value.

In a parametrized scenario, the label must be the same in every case. If the content differs between cases, it becomes a column in the parameter table, named after the label. The step shows a badge that points to that column (see [Parametrized scenarios](parametrized.md)).

