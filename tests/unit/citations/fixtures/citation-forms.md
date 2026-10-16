# Citation forms

The work is done ✅
[A scenario title](https://example.org/report.html#scenario=tests/t.py::test_a)

> 🔵 [A title wrapped
> across lines](https://example.org/report.html#tag=spec/x) (1 ✅ · 1 🔵)

| Kind | Citation |
|---|---|
| tag | ✅ [spec/x](https://example.org/report.html#tag=spec/x) (2 ✅) |
| scenario | ❌ [the `a\|b` form](https://example.org/report.html#scenario=t.py::test_b) |

- ✅ [In a bullet](https://example.org/report.html#scenario=t.py::test_c)
- Is it done? [plain](https://example.org/report.html#scenario=t.py::test_d)

```markdown
✅ [Shown, not read](https://example.org/report.html#scenario=t.py::test_e)
```

## Edge cases

### Escapes and entity references in a destination

[Escaped destination](https://example.org/edge/14?a\_b&amp;c=\&amp;&#35;d)

### A table right after a paragraph's text

The table interrupts this paragraph:
| Kind | Link |
|---|---|
| tag | [Interrupting table](https://example.org/edge/15) |
