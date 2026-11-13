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

The Glossary view lists the terms, with a search and a filter for undefined terms. The search also matches a term's [avoided words](guide/glossary.md#avoided-words). Expand a term to see its avoided words, as `Avoid: Customer, Client`, and the stories and scenarios that use it. Select *Show N scenarios using this term* to filter the Scenarios view by it.

The view groups the terms by section or by kind:

- **By section**, for a glossary with [glossary sections](guide/glossary.md#glossary-sections). The sections come in the order the glossary first names each one. A section named **Other**, in any case, comes last, and the terms with no section join it. When no section has that name, the terms with no section form an **Other** group of their own. The sidebar lists the sections with their term counts. Click a section to show only its terms, and click more to show the terms of any of them. With none selected, every section shows.
- **By kind**, for a glossary whose terms have kinds. The sidebar has a checkbox per kind to show or hide its terms.

A glossary with sections opens grouped by section. When at least one of its terms has a kind, a *Group by* switch at the top of the sidebar changes between *Section* and *Kind*, and switching to *Kind* clears the section selection. A glossary with neither sections nor kinds lists its terms without groups.

A glossary counts as having sections only when its terms name at least two. A glossary under a single heading shows no sections.

## Links

The address bar always holds the current view: its filters, status toggles and search. Copy it to share exactly what you see. A link can also open a single scenario, tag, story or glossary term. The copy button on a scenario card, a story header, a Tags sidebar row or a Glossary term row copies such a link, or a [citation](guide/citations.md) for a Markdown document. When a link names something the report no longer has, the report says so and opens without it.

Each section header in the Glossary view has a link button, which copies a link that opens the Glossary with that section alone selected. A section link is no citation: `pytest-given citations check` doesn't check it.

## Publishing

Copy buttons put a citation on the clipboard only when the report knows its public URL. Set it with `--given-report-url` (ini setting `given_report_url`). A report served from several places can be rendered once per place from the same JSON with the [standalone CLI](cli.md), each with its own `--report-url`. This site does that for its [example reports](examples.md).

For a text version of the same run, see the [Markdown report](markdown-report.md).
