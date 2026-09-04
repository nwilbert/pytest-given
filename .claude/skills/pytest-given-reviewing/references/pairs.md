# Narration/body pairs from the JSON report

Layer 2 needs each step's text and the code under it side by side. Every scenario in the JSON sink carries its `source` (`relpath` + `line`), so one pass pairs each narration with the whole test function carrying it, grouped by test file.

```bash
pytest <selection> --given-json=report.json
python pairs.py report.json dump/     # the script below
```

Run it from the rootdir — the `relpath`s are relative to it.

## The script

```python
# usage: python pairs.py <report.json> <out-dir>
import ast, collections, json, pathlib, sys

report, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
scenarios = json.loads(report.read_text(encoding='utf-8'))['scenarios']
by_file = collections.defaultdict(list)
for scenario in scenarios:
    by_file[scenario['source']['relpath']].append(scenario)

out.mkdir(parents=True, exist_ok=True)
for relpath, group in sorted(by_file.items()):
    source = pathlib.Path(relpath).read_text(encoding='utf-8')
    lines = source.splitlines()
    spans = [
        (min([node.lineno] + [d.lineno for d in node.decorator_list]), node.end_lineno)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    chunks = []
    for scenario in sorted(group, key=lambda s: s['source']['line']):
        anchor = scenario['source']['line']
        # The innermost function whose span (decorators included) holds the
        # anchor: a test defined inside a helper still resolves to the test.
        enclosing = sorted(
            (span for span in spans if span[0] <= anchor <= span[1]),
            key=lambda span: span[1] - span[0],
        )
        if not enclosing:
            chunks.append(f'### {relpath}:{anchor} — no function found\n')
            continue
        start, end = enclosing[0]
        body = '\n'.join(f'{n}\t{lines[n - 1]}' for n in range(start, end + 1))
        chunks.append(
            f'### {relpath}:{anchor} [{scenario["status"]}] '
            f'[tags: {", ".join(scenario["tags"]) or "-"}] '
            f'[story: {scenario["story_id"] or "-"}]\n'
            f'TITLE: {scenario["narration"]["text"]}\n{body}\n'
        )
    path = out / (relpath.replace('/', '__') + '.txt')
    path.write_text('\n'.join(chunks), encoding='utf-8')
    print(f'{len(group):4d} scenarios  {path}')
```

## Reading the dump

- Each entry is the report's title over the test's source, decorators included, with real line numbers — cite `file:line` straight from the dump.
- A parametrized scenario appears once, anchored where the report anchors it; its parameter table stays in the JSON.
- Only decorated tests are in the report, so only they are in the dump — a suite passed to an inner run as a string literal never appears; read the literal.
- One file per test file is the fan-out unit: hand a reviewer that file and the layer-2 rubric, nothing else.
- `--given-json` is a plain pytest flag, so this needs no project wiring and no other sink.
