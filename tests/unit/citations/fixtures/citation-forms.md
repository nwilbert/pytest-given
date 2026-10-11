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

### An empty sibling item after a paragraph

- a
-
    four [Empty sibling item](https://example.org/edge/1)

### An empty sibling item before a tab

- a
-
	Tab [Empty sibling item, tab](https://example.org/edge/2)

### A lazy setext line under a list item

- a
===
    four [Lazy setext line](https://example.org/edge/3)

### A lazy setext line outside a quote

> p
===
    four [Lazy quoted setext line](https://example.org/edge/4)

### A bare quote marker ends the list item

- item
>
    code [Bare quote marker](https://example.org/edge/5)

### A bare quote marker ends a fence in a list item

2) two
    ```
>

	Tab [Fence ended by a quote marker](https://example.org/edge/6)

### A blank line leaves the list item's quote

> - a

>     code [Blank line leaves the quote](https://example.org/edge/7)

### An empty item ends at a blank line

-

    four [Empty item, blank line](https://example.org/edge/8)

### An ordered item from 2 interrupts no paragraph

p
2) d

    four [Ordered from 2](https://example.org/edge/9)

### An empty item interrupts no paragraph

p
*
        eight [Empty item after a paragraph](https://example.org/edge/10)

### A lazy line outside a quote opens a list

> p
2) d

    four [Lazy line opens a list](https://example.org/edge/11)

### An indented quote marker after a bare one

- item
>
    > k [Indented quote marker](https://example.org/edge/12)

### An indented fence opener on a lazy line

> > h
    ``` [Indented fence opener](https://example.org/edge/13)

### Escapes and entity references in a destination

[Escaped destination](https://example.org/edge/14?a\_b&amp;c=\&amp;&#35;d)
