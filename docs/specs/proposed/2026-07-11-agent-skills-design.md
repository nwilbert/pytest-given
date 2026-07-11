# Agent Skills — Design Spec

## Goal

Ship **agent skills** with pytest-given so downstream projects can hand their coding agents proven guidance on authoring, navigating, and reviewing pytest-given artifacts (scenarios, glossaries, stories). The skills are plain [Agent Skills](https://agentskills.io) directories (`SKILL.md` + reference files) — the open format Claude Code and other harnesses discover natively — installed into a downstream repo via a new CLI subcommand:

```bash
pytest-given skills install            # copies into ./.claude/skills/
pytest-given skills install --check    # exit 1 if installed files drift from the bundled ones
```

The portable narration rules in [AGENTS.md](../../AGENTS.md#narration-rules-portable) move into the authoring skill and this repo becomes the skills' first consumer: contributor agents auto-discover them from `.claude/skills/`, and AGENTS.md keeps only the repo-specific self-report mechanics. This resolves the "provide an agent skill" item in [TODO.md](../../TODO.md).

## Background

Part of pytest-given's value proposition is agent-legible tests: narration in glossary vocabulary, stories as the actor-level view, reports an agent can read instead of reverse-engineering code. (The reports serve human readers just as much — the skills address the agent-facing half.) The knowledge of *how to write and use* these artifacts currently lives only in this repo's AGENTS.md — already marked "portable … the seed of the planned downstream skill" — where no downstream project can see it. Skills are the distribution vehicle: a slim always-discoverable `SKILL.md` router whose detailed guides load into context only when the activity at hand needs them (progressive disclosure), exactly the modular shape this content wants.

## The three skills

| Skill | Description (triggering conditions) | Phase |
|---|---|---|
| `pytest-given-authoring` | Use when writing or changing `@scenario` tests, glossary terms, or domain stories in a project using pytest-given | **1 (this spec's implementation)** |
| `pytest-given-navigating` | Use when exploring or trying to understand a codebase that has pytest-given artifacts (`@scenario` tests, a glossary, stories) — the reports are the map, not the code | 2 |
| `pytest-given-reviewing` | Use when reviewing changes to scenarios, stories, or a glossary — narration truthfulness, lint findings, term coverage | 3 |

Decisions baked into the table:

- **Three skills, not one.** Authoring, navigating, and reviewing have genuinely different triggering situations; separate skills give each a crisp "Use when…" description, which is what a harness matches against. Shared material is not duplicated: the reviewing skill will reference the authoring skill's `references/scenarios.md` by relative path (`../pytest-given-authoring/references/`), safe because the installer always installs the set together.
- **`pytest-given-` name prefix.** The skills land in the downstream repo's flat `.claude/skills/` namespace alongside unrelated skills; the prefix prevents collisions and makes provenance obvious.
- **Descriptions state only triggering conditions, never workflow.** A description that summarizes the process becomes a shortcut agents follow instead of reading the skill body.

Phases 2 and 3 are content sketches only (see [Later phases](#later-phases-sketch)); everything else in this spec is phase 1.

## Source layout: `.claude/skills/` is canonical

The skill directories live directly in this repo's `.claude/skills/`, committed:

```
.claude/skills/
  pytest-given-authoring/
    SKILL.md                      # slim router, target <500 words
    references/
      scenarios.md                # the portable narration rules, generalized
      glossaries.md               # authoring glossaries
      stories.md                  # authoring stories
      domain-storytelling.md      # general Domain Storytelling concepts
```

Why there and not a root `skills/` directory: Claude Code auto-discovers project skills only from `.claude/skills/`, so the canonical location *is* the dogfooding location — this repo's contributor agents pick the skills up with zero duplication and no sync check. (Symlinks were rejected: unreliable on the Windows-checkout/WSL seam this project supports.) A later plugin-marketplace wrapper can point at the same directory.

## The authoring skill

### `SKILL.md` (router)

Always loaded when triggered, so it stays slim. Contents:

- **Core principle:** the narration is the spec — write the scenario name and step texts before the step bodies, then make the code fill them in.
- **Adoption guidance:** each artifact kind stands on its own — scenarios-only is a perfectly good adoption level — but they compound when combined: scenarios narrate in glossary vocabulary (term refs power the per-term filter), and stories give the actor-level view scenarios link into. The natural adoption order depends on the project: in an **existing codebase**, start with scenarios (decorate the tests you have) and let glossary terms emerge from their narration; in a **greenfield project**, consider starting with stories — transferring the results of Domain Storytelling sessions with stakeholders into code before any scenarios exist, so the domain understanding and vocabulary are established up front. The glossary either pre-exists (adopt it as `GLOSSARY.md`) or is discovered from scenarios and stories along the way.
- **Routing table:** read `references/scenarios.md` when decorating or editing tests; `references/glossaries.md` when adding, renaming, or reorganizing terms; `references/stories.md` when writing or extending stories; `references/domain-storytelling.md` for the underlying concepts (first story in a project, or modeling questions like actors vs. work objects).
- **Verification hook:** render touched scenarios (`pytest <selection> --given-md`) and read the output as a spec; run the narration lint if the project enables it.

### `references/scenarios.md`

The [portable narration rules](../../AGENTS.md#narration-rules-portable) from AGENTS.md, moved (not copied) and generalized:

- Repo-specific references are replaced: the `pg` glossary handle, `tests/_vocab.py`, `test_story.py`/`test_glossary.py` pointers, the `self_report` nox session, and ruff `SIM117` notes give way to generic phrasing and coffeeshop-style examples.
- Each rule keeps its structure: bolded imperative, then the reasoning. The rules are the product of real authoring iterations; the generalization must not flatten them into platitudes.
- The lint rule names (`missing-phase`, `empty-step`, `action-in-then`, …) stay mentioned as the mechanical counterparts, since downstream projects have the same linter.

### `references/glossaries.md`, `references/stories.md`, `references/domain-storytelling.md`

New content, written fresh from the README and design specs ([file-backed glossary](../2026-06-18-file-backed-glossary-design.md), [domain storytelling](../2026-06-07-domain-storytelling-design.md), [bare strings in activity paths](../2026-06-27-bare-strings-in-activity-paths-design.md)):

- **glossaries.md** — `FileGlossary`/`GLOSSARY.md` as the recommended default (a Markdown table humans and agents both read), code-defined `Glossary` as the alternative; term naming (natural-language headers, not class names; the `id_derive` slug as the lookup key and why renames are code changes); kinds; keeping tags orthogonal to terms.
- **stories.md** — `story()` mechanics: activity paths, actors, work objects, sentence grammar, linking scenarios to story steps; when a story earns its keep vs. scenarios alone.
- **domain-storytelling.md** — the method behind the feature: actors, work objects, activities, the pictographic-sentence model, granularity levels; how pytest-given's story grammar maps onto it. Cites [domainstorytelling.org](https://domainstorytelling.org/) as the canonical reference (the method's official home: quick-start guide, the Hofer/Schwentner book, the Egon.io modeling tool) rather than restating the method in full. Deliberately optional background — the router sends agents here only for conceptual questions.

## AGENTS.md restructure

- The "Narration rules (portable)" subsection is **deleted**; "Writing self-report scenarios" shrinks to the repo-specific mechanics plus one line pointing at the `pytest-given-authoring` skill (which contributor agents auto-discover anyway).
- Cross-references to the portable rules (quality gates, lint spec pointers) are updated to point at the skill file.

## CLI: `pytest-given skills`

### Entry-point promotion

The console script currently points at `pytest_given.report.cli:main`. A `skills` subcommand does not belong to the `report/` subpackage, so a new top-level `src/pytest_given/cli.py` takes over the entry point (`pytest-given = "pytest_given.cli:main"`): it owns the argparse root and subparsers, delegates `report` to the existing machinery in `report/cli.py`, and implements `skills` itself (it is small — resource listing, file copy, diff). Like `plugin.py`, the top-level `cli.py` may import from any subpackage.

### Semantics

- `pytest-given skills install [--dest DIR]` — copies every bundled skill directory into `DIR` (default `./.claude/skills/`), creating parents, **overwriting existing files**, and printing the files written. The skill files are library-owned: local edits are clobbered on reinstall, and the docs say so — downstream customization belongs in the project's own skills or instructions file, not in edits to these files.
- `pytest-given skills install --check` — writes nothing; exits 1 listing files that are missing or differ from the bundled versions, 0 when in sync. This is the post-upgrade drift detector, CI-friendly.
- Both operations touch **only the bundled `pytest-given-*` skill directories**: the destination is a shared namespace holding the downstream project's own skills, which install never overwrites and `--check` never reports. Stale files *inside* a bundled skill directory (left over from a version that shipped a file the current one doesn't) are removed on install and flagged by `--check`, so each owned directory is an exact mirror.

### Packaging

Hatchling `force-include` maps `.claude/skills/` into the wheel as `pytest_given/skills_data/` (a data directory, not a package — the name avoids clashing with any future `skills/` subpackage). The installer walks it via `importlib.resources`. sdists include the directory through the same mapping.

## Testing

Two mechanical layers plus the skill-content gate:

1. **Packaging test** — a unit test asserts the resources visible through `importlib.resources` match the repo's `.claude/skills/` tree byte-for-byte, so the force-include mapping can't silently rot.
2. **Installer tests** — `install` into a `tmp_path` (fresh, and over a stale copy to prove overwrite), `--check` in the in-sync / drifted / missing cases, `--dest` handling.
3. **Skill baseline test (RED/GREEN)** — before the authoring skill ships, run a subagent on a realistic "decorate this test with `@scenario`" task *without* the skill and record the failure modes (expected: folded constructor, missing `when`, placeholder steps, narration written after the code); then rerun with the skill installed and verify the failures disappear. The recorded baseline goes in the PR description, not the repo.

## Later phases (sketch)

- **Phase 2, `pytest-given-navigating`:** how to read a codebase through its reports — `--given-md` for prose, `--given-json` + `jq` for filtering by tag/term/status, the glossary as the domain map, stories as the interaction map, source links back to code. Seed material: the "Handling report output" section of AGENTS.md, generalized.
- **Phase 3, `pytest-given-reviewing`:** the narration lint as the structural gate; the semantic audit (does each step text match its body?) as a per-file fan-out to cheap fast-model subagents (TODO.md's haiku-reviewer idea; phrased harness-neutrally — audit inline where subagents aren't available). Semantic truth is exactly what the [lint spec](../2026-07-05-narration-lint-design.md) declared out of mechanical reach, and its anticipated `audit` command (serializing the already-captured `Step.source` ranges into (step text, body source) pairs) is the natural input feed — phase 3 may be what motivates building it. The judge takes the narration rules as its rubric (step text may abstract, never overstate), and findings are advisory review comments, not an exit code. Plus glossary/story review: term coverage, `tag-shadows-term`, dead terms. References the authoring skill's `scenarios.md` rather than restating it.
- **Maybe later:** a Claude Code plugin-marketplace wrapper around the same `.claude/skills/` directory, for `/plugin`-based updates.

## Out of scope

- Any change to report artifacts, the plugin, or the lint — this feature is docs + CLI only.
- Auto-installing skills on `pip install` or at pytest startup (surprising side effects; explicit install only).
- Per-harness install targets beyond `.claude/skills/` (`--dest` already covers other layouts).
