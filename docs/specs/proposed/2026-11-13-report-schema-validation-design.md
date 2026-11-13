# Report Schema and Validation — Design Spec

## Goal

Define the JSON report and the delta report by a published JSON Schema, and read both through Pydantic validation, so that:

- a malformed or foreign report fails with the path and reason of each problem (`scenarios.3.status: Input should be 'passed', 'failed', 'skipped' or 'xfailed'`), not a wrapped `KeyError`;
- tools other than pytest-given — `jq` users, editors, scripts — have a contract for the JSON they read;
- the hand-written readers in `model/serde.py` and `model/delta_serde.py` give way to one declaration of the shape: the dataclasses that already exist.

## Non-goals

- Reading any schema version other than the current one. JSON reports from older versions stay unsupported, as AGENTS.md says, and a version mismatch is a plain error. An older report as the before side of `pytest-given delta` is the one case that may want more, and this design leaves room for it (see [Versioning](#versioning)).
- Validating the model as capture builds it. Validation happens where a report dict is read: a JSON file from disk, and the dict a session is about to write (see [Writing](#writing)).
- A `type` tag on the members of a union. Each variant already has required keys no other variant has, and a tag on every narration part grows a typical report by 10–15%.
- One error per mistake inside a union. A malformed union member fails every variant, and the message lists each variant's errors (see [Unions](#unions)). Only a hand-edited report gets there, and nothing calls for editing one.
- Descriptions in the schema. A field's would need `Field(description=…)` on the dataclasses and pull Pydantic into the model. A class's would be its docstring, which is written for contributors (see [Committed schemas](#committed-schemas)). A later change can add them.
- A `pytest-given schema` command or shipping the schema files in the wheel.

## Anti-goals

- Pydantic types in the model. `model/schema.py` and `model/delta.py` keep stdlib dataclasses: no `BaseModel`, no `pydantic.dataclasses`, no `Field`, no `Discriminator` marker. Pydantic appears only in the module that holds the document types (see [Reading](#reading)).
- Pydantic imported by a plain `pytest` run that writes no report, on Python 3.15. Python 3.14 has no lazy imports, so every run imports it there.
- A published schema that disagrees with the JSON written. Two tests hold them together (see [Committed schemas](#committed-schemas)).

## Versioning

Both reports carry their version as an integer, `metadata.schema_version`, as now. The first version under this design is **1** for the report and **1** for the delta. No released pytest-given (≤ 0.5.2) writes a `schema_version`, so no report in the wild claims version 1 with another shape. The `$schema` key this design adds therefore needs no bump: version 1 *is* the shape this design defines.

The reader checks `schema_version` before validating the rest, so a report or delta of another version gets a one-line message, not a list of field errors:

- `delta_from_dict` has that check (`_refuse_another_schema_version` in `model/delta_serde.py`).
- `report_from_dict` gains the same check with the same wording. `pytest-given report` and `pytest-given citations` then refuse a report of another version, which includes every report written by pytest-given ≤ 0.5.2.
- `check_schema_versions` in `delta/check.py` stays. `pytest-given delta` runs it before reading either report, and its message names both.

The type of the field is `Literal[1]` (resp. the delta's), so validation would refuse another version anyway, and the schema states the version as a constant. The pre-check exists for the message. The number then stands in the annotation and in `REPORT_SCHEMA_VERSION` / `DELTA_SCHEMA_VERSION`. *Builder's call:* how the two are held equal.

Each report also carries a top-level `"$schema"` key with the URL of its schema file (see [Hosting](#hosting)). It is there for editors, which validate and autocomplete a JSON file by it. The reader does not use its value: a report without `$schema` reads the same, and nothing parses a version out of the URL.

The rule in AGENTS.md stays: bump `REPORT_SCHEMA_VERSION` / `DELTA_SCHEMA_VERSION` in the same commit as any change to the JSON's shape, an added optional field included. The check enforcing it becomes the committed-schema test, replacing the fingerprint test in `tests/unit/model/test_schema_version.py`.

A report of another version is regenerated, never converted: run the suite again under the current pytest-given, as the `pytest-given-delta` skill describes for the older side of a delta.

A later change may let `pytest-given delta` take an older report as its before side. It would convert the dict to the current version's shape before the pre-check, one step per version, and everything after that stays as designed here. This design keeps what that needs: the integer version in every report, and every version's schema file. It does not answer how such a delta compares. A field the older version did not record has no value to compare, and filling in its default would show in the delta as a change. That question belongs to a spec of its own.

## Reading

A new module in `model/` holds one document type per report kind: `ReportDocument` and `DeltaDocument`, each a Pydantic `BaseModel` describing the whole written JSON. Its fields are the root dataclass's fields (`ReportData`, `DeltaData`), `$schema` by alias, and for the report the derived `coverage` section. The field types are the existing stdlib dataclasses. Pydantic validates those directly, including `NewType` ids, `Literal` aliases, PEP 695 `type` aliases, tuples, and optional fields with defaults.

The root is a model because a model takes configuration and passes it on to the stdlib dataclasses nested in it. A `TypeAdapter` over the root dataclass refuses a `config` argument. The configuration:

- `extra='forbid'`: an unknown key anywhere fails with its path (`scenarios.0.stauts: Unexpected keyword argument`).
- `json_schema_serialization_defaults_required=True`, for the schema (see [Committed schemas](#committed-schemas)).

*Builder's call:* whether the document types restate the root dataclass's few fields, with a test holding the two equal, or are built from `dataclasses.fields`.

The `*_from_dict` functions shrink to:

1. the pre-checks that give a better message than validation would: a delta passed where a report is expected and vice versa (`is_delta_dict`), and the schema-version mismatch;
2. validation through the document type, whose fields make the root dataclass;
3. the checks that are not shape: `resolve_report_url` on `metadata.report_url`, for the report and for each of the delta's two sides, and the delta's cross-reference checks (`_check_sides`, `_check_lookups`, the table-pairing check). These run on the validated dataclasses and surface as `PytestGivenError`, as now. *Builder's call:* what an empty `report_url` string does, which no writer produces.

Validation runs each dataclass's `__post_init__`. `Glossary` builds its indexes there, and its `init=False` index fields are not expected in the JSON. `Definition`'s assertion that its parts spell its text fails as a validation error at the definition's path.

A `ValidationError` becomes a `PytestGivenError` naming the source and listing each error as `<dotted path>: <message>`, without Pydantic's documentation URLs (`errors(include_url=False)`). *Builder's call:* how many errors to list before "and N more".

Validation runs in Pydantic's lax mode: `"12"` is accepted as 12 where the type is an integer. Strict mode refuses a dict where the type is a dataclass, so it would need the JSON text, and the readers take a dict. The schema is the contract for what is written. The reader accepts slightly more.

Refusing unknown keys costs no compatibility between versions. The version pre-check runs first, so a reader never validates a report whose version has keys it does not know.

`$schema` and `coverage` are optional on read and their values unused. A session validates its dict before either is added, and `coverage` is derived again on every write.

The public names stay: `report_from_dict`, `delta_from_dict`, `read_report_json`, `report_to_dict`, `delta_to_dict`. Call sites in `cli/`, `report/`, `plugin/` do not change.

### Unions

The unions of dataclasses stay untagged and unmarked:

| Alias | Variants |
|---|---|
| `NarrationPart` | `NarrationLiteral`, `NarrationValue`, `NarrationPlaceholder`, `NarrationTermRef` |
| `DefinitionPart` | `NarrationLiteral`, `NarrationTermRef` |
| `ClausePart` | `ClauseTermRef`, `ClauseWord` |
| `StepAttachment` | `Attachment`, `AttachmentRef` |
| `CellValue` | a scalar, `Attachment` |

Pydantic's smart-mode union picks the variant. Each variant has required keys no other variant of its union has, so exactly one matches a valid member. The schema shows each union as an `anyOf` of its variants.

A malformed member matches no variant, and Pydantic then reports every variant's errors. A narration literal whose `value` is a number gives seven lines: the one about `value`, and a `Field required` for each required key of the other three variants. The message lists them as they come.

## Writing

The writer stays `asdict_filtered` — reflective, no Pydantic — and every written JSON gains the top-level `$schema` key with the current version's URL. *Builder's call:* whether `report_to_dict` / `delta_to_dict` or the JSON sinks add it.

`asdict_filtered` skips `_`-prefixed fields and fields marked `serde_exclude`. The schema generator skips the same fields, by one predicate both call, so the `Glossary` indexes and `Step.source` are in neither the JSON nor the schema.

A session that writes any report validates: `render_sinks` reads its own dict back through `report_from_dict` before rendering HTML and Markdown. So every report-writing run checks what it wrote against the reader, and imports Pydantic. Validating costs about what the hand-written reader does: 7.0 ms against 6.3 ms for the self-report's 313 scenarios. The new cost is at start-up, importing Pydantic and building the document type's validator, about 0.1 s together once the files are cached. Run `uv run nox -s benchmark` before and after and compare the session's wall time, not only the rendering.

The written report is `ReportData` plus the derived `coverage` section that `render_json` adds, and `$schema`. `ReportDocument` describes exactly that. `CoverageRecord`, a `TypedDict` in `report/story_view.py` holding only ids and a boolean, moves to `model/` so the document type can name it.

Defining a `BaseModel` imports Pydantic, which is why the document types have a module of their own. The serde modules list that module in `__lazy_modules__`, and it lists `pydantic` in its own. The lazy-import test (`tests/integration/test_lazy_imports.py`) holds a run that writes no report to not importing Pydantic.

## Committed schemas

The schema files are generated from the document types, committed, and checked:

- `docs/site/schemas/report-v1.schema.json` and `docs/site/schemas/delta-v1.schema.json`, one file per version. Every bump adds a file next to the earlier ones, a bump between two releases included.
- Once a release has written reports of a version, that version's file is not changed to accept other JSON. That is a convention: no test tells a released version's file from an unreleased one.
- A change in how the schema is written that leaves the accepted JSON the same regenerates the current version's file in place, with no bump. A renamed dataclass is one, since its name is a key under `$defs`. A Pydantic upgrade can be another.
- Generated in **serialization mode** with defaults required, so every field the writer always emits is `required`, even when its dataclass field has a default. A reader of the JSON should not have to guard against an absent `status`. `$schema` and `coverage` are required too, and `$schema` is a string.
- Every object says `additionalProperties: false`, which follows from `extra='forbid'`.
- Draft 2020-12, with `$schema` and `$id` added by a small `GenerateJsonSchema` subclass. `$id` is the file's hosted URL. The same subclass leaves out the fields the writer skips (see [Writing](#writing)).
- That subclass also leaves out each class's `description`. Pydantic 2.14 copies a dataclass's docstring there. The docstrings are written for contributors, and with them in the schema an edited docstring would change the committed file.
- The file is generated under the locked Pydantic, which must be 2.14 or later. Earlier versions validate the same but write another schema: the root's configuration does not reach the nested dataclasses there, so `additionalProperties` and the required defaults are missing.
- **The committed-schema test** generates the current version's schema and compares it with the committed file of that version. It holds the file to the types. A shape change fails it, and its message says to bump the version and commit the new file, as the fingerprint test's does now. It runs only under the locked Pydantic, so `compat` skips it. *Builder's call:* how the test tells.
- **The written-JSON test** validates JSON from the current writer against the committed schema with a standard validator (`jsonschema`): a report with a glossary, stories and a parameter table, and a delta. It holds the schema to the writer, which the committed-schema test cannot. The JSON comes from the test run, not from a committed example, which can be older than the writer.
- A nox step or a small script regenerates the file. *Builder's call:* whether it is its own session or part of `self_report`/`examples`.

## Hosting

The docs site serves the schema files at `https://nwilbert.github.io/pytest-given/latest/schemas/report-v1.schema.json` (and the delta's), which is also each file's `$id` and the `$schema` value a report carries. Because old version files stay in the folder, a report's `$schema` link keeps resolving after later versions arrive.

`latest` moves only when a release publishes its docs. A report written from `main` after a bump therefore links to a file that is not served until the next release. An editor that cannot fetch a schema skips validation, and that is accepted.

Zensical copies non-Markdown files under `docs/site/` as they are. Confirm with `uv run nox -s docs_build` that `.json` files are served unchanged, and on the published site that the `latest` alias serves them: an alias made of redirect pages covers HTML only.

## Dependency

`pydantic` joins `[project] dependencies`. *Builder's call:* the floor. It must be the lowest version that installs on both Python 3.14 and 3.15 and validates as this design needs: stdlib dataclasses nested in a model, with the model's `extra='forbid'` reaching them. Pydantic 2.12.0, the first for Python 3.14, does. Generating the schema needs 2.14, which only the locked version has to meet (see [Committed schemas](#committed-schemas)). The `compat` session gains it as a third floor, pinned at the floor for the oldest run and unpinned for the newest, as pytest and markdown-it-py are. That session runs the floor on both Pythons.

`jsonschema` joins the `test` dependency group for the written-JSON test.

## Documentation

- A docs page section on the JSON report's schema: where the file is, that `schema_version` is the version, that only the current version is read. *Builder's call:* whether that goes on an existing page (`cli.md`, `configuration/pytest-options.md`) or a new one. The delta report's page gets the same for the delta schema.
- `docs/site/cli.md` says that `pytest-given report` and `pytest-given citations` exit 2 on a report of another schema version, as it says for `pytest-given delta` now.
- The navigating skill's `jq` guidance (`src/pytest_given/.agents/skills/pytest-given-navigating/`) points at the schema file for the full shape.
- AGENTS.md's schema-version convention names the committed-schema test instead of the fingerprint test.
- CHANGELOG, under **Added**: the published schemas, the `$schema` key, and the path-and-reason errors. A **Breaking** entry: `pytest-given report` and `pytest-given citations` refuse a JSON report of another schema version or with an unknown key, which includes every report written by 0.5.2 or earlier. The migration is to regenerate the report.

## Done when

- `report_from_dict` and `delta_from_dict` validate through the document types, and the hand-written per-class readers are gone.
- A malformed report fails with the dotted path of each problem, an unknown key included. A report of another schema version gets the one-line mismatch message, from `pytest-given report` and `pytest-given citations` as from `pytest-given delta`.
- `report-v1.schema.json` and `delta-v1.schema.json` are committed, served from the docs site, and held to the types by the committed-schema test, which replaced the fingerprint test.
- Every written report and delta carries `$schema`, and the written-JSON test validates both against their committed schemas.
- The example reports, the example delta and the self-report are regenerated and committed, since each JSON gains `$schema`.
- The self-report has a scenario for each new rule: a malformed report is refused with the path and reason of each problem, a report of another schema version is refused, and a written report names its schema.
- A plain `pytest` run without report flags does not import Pydantic on Python 3.15, and the benchmark shows no regression in session wall time worth acting on.
- `uv run nox` and `uv run nox -s compat` pass.
