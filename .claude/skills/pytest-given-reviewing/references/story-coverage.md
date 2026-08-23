# Story coverage from the JSON report

The Stories tab shows a coverage chip per activity, but it is HTML, and `--given-md` has no Stories section at all. From a terminal, compute coverage from the JSON sink: `pytest <selection> --given-json=report.json`.

## The matching rule

An activity is covered when **one single step's** term refs include **all** of the activity's terms.

- Refs spread across several steps never add up — matching is per step, not against their union.
- Terms in the `@scenario` name don't count; only step narration does.
- An activity with fewer than two distinct terms is not coverage-tracked at all, and renders as such.
- A step pinned with `activity=` covers exactly the activities it names, regardless of what the narration references — and *only* those: a pinned step is skipped by narration matching entirely, so it cannot also cover a different activity its text happens to fit.
- A scenario carrying `activity_ids` is scoped to those activities and can cover no others.
- Matching is on *identities*, not bare term ids: a verb contributes its canonical identity whatever its inflection, while an actor or work object written as an instance (`guest('Alice')`) contributes that instance. A step's instance ref also contributes the canonical, but not the reverse — so a canonical step ref does **not** cover an instance-anchored activity.

## The query

```python
# uncovered activities, from `pytest <selection> --given-json=report.json`
import json, sys
d = json.load(open(sys.argv[1]))
bound = {}
for s in d['scenarios']:
    bound.setdefault(s.get('story_id'), []).append(s)

def walk(steps):
    for st in steps:
        yield st, {p['term_id'] for p in st['narration']['parts'] if 'term_id' in p}
        yield from walk(st['children'])

for story in d['stories']:
    for a in story['activities']:
        want = {p['term_id'] for pa in a['paths'] for p in pa['parts'] if 'term_id' in p}
        if len(want) < 2:
            continue  # under-anchored: not coverage-tracked
        if not any(
            want <= refs or a['id'] in st['activity_ids']
            for s in bound.get(story['id'], [])
            if not s['activity_ids'] or a['id'] in s['activity_ids']
            for st, refs in walk(s['steps'])
        ):
            print(f'UNCOVERED {story["id"]}#{a["id"]}')
```

It matches on term ids alone, and it lets a pinned step match by narration as well as by its pin — two ways it can call an activity covered when the report won't. Treat its output as a **floor** on what is uncovered. Tighten it by comparing `display` values when the story under review uses instances.
