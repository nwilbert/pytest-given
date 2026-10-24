# HTML report

The HTML report is one self-contained file: no server, no external assets. Open it locally, keep it as a CI artifact, or publish it on your docs site. The [Coffeeshop report](examples/coffeeshop.html){ target=_blank } shows the core features, and the [Hotel booking report](examples/hotel-booking.html){ target=_blank } adds a glossary and stories.

```bash
pytest --given-html              # writes given-report/report.html
pytest --given-html=report.html  # or a path of your own
```

The report has up to three views, switched in the top bar: **Scenarios**, **Stories** if you declare [domain stories](guide/domain-storytelling.md), and **Glossary** if you register a [glossary](guide/glossary.md). The top bar also switches the theme (see `--given-theme` under [pytest options](configuration/pytest-options.md#flags)).

## Scenarios

Each scenario is a card: its title, tags, status and duration. Click it to see its steps, parameter table and error, and the test's file and line, which `--given-source-link` turns into a [source link](configuration/source-links.md). A step with nested steps expands on click.

To narrow the list down, the sidebar offers:

- **Search**, which matches scenario titles and tags.
- **Status** toggles, to show or hide the scenarios of each status.
- **Browse by** Modules, Tags or, with a glossary, Terms: a tree of groups with their scenario counts, sorted by name or by count. Selecting a group filters the list to it. [Nested tags](guide/scenarios.md) form a tree, and selecting a heading shows all tags below it.

Each module, tag, term and story sentence filter shows as a chip above the list, where you can clear it on its own. Tag and term filters stack: a scenario must match all of them. Clicking a tag on a card filters by it as well.

In a [parametrized scenario](guide/parametrized.md), hover a column of the parameter table to highlight its placeholders in the steps. Hover a row to see the steps with that case's values filled in. Hover a [term ref](guide/glossary.md) to see the term's definition, and click it to open the term in the Glossary view.

## Stories and Glossary

The Stories view shows each story as a timeline of its sentences, with the scenarios that cover each one. See [Coverage in the report](guide/domain-storytelling.md#coverage-in-the-report).

The Glossary view lists the terms by kind, with a search and filters for kind and for undefined terms. Expand a term to see the stories and scenarios that use it, and select *Show N scenarios using this term* to filter the Scenarios view by it.

## Links

The address bar always holds the current view: its filters, status toggles and search. Copy it to share exactly what you see. A link can also open a single scenario, tag or story. The copy button on a scenario card, a story header or a Tags sidebar row copies such a link, or a [citation](guide/citations.md) for a Markdown document. When a link names something the report no longer has, the report says so and opens without it.

## Publishing

Copy buttons put a citation on the clipboard only when the report knows its public URL. Set it with `--given-report-url` (ini setting `given_report_url`). A report served from several places can be rendered once per place from the same JSON with the [standalone CLI](cli.md), each with its own `--report-url`. This site does that for its [example reports](examples.md).

For a text version of the same run, see the [Markdown report](markdown-report.md).
