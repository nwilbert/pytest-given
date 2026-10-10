# Narration/body pairs from the JSON report

Layer 2 needs each step's text next to the code under it. Every scenario in the JSON report has its `source` (`relpath` and `line`). So one pass can pair each scenario's narration with its whole test function, grouped by test file.

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
            f'[stories: {", ".join(scenario["story_ids"]) or "-"}]\n'
            f'TITLE: {scenario["narration"]["text"]}\n{body}\n'
        )
    path = out / (relpath.replace('/', '__') + '.txt')
    path.write_text('\n'.join(chunks), encoding='utf-8')
    print(f'{len(group):4d} scenarios  {path}')
```

## Reading the dump

- Each entry shows the report's title above the test's source, including decorators, with real line numbers. Cite `file:line` straight from the dump.
- A parametrized scenario appears once, at the line the report points to. Its parameter table is only in the JSON.
- Only decorated tests are in the report, so only they are in the dump.
- The dump holds only the test function. A module-level constant or helper that the body uses (a suite string, a record builder) is elsewhere in the test file, so open the file before you judge a value.
- When you split the audit, one dump file is one reviewer's share: hand a reviewer that file and the layer-2 rubric, nothing else.
- `--given-json` is a plain pytest flag, so this needs no project setup and no other report format.
