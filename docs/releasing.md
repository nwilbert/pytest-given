# Releasing pytest-given to PyPI

Releases are cut by manually dispatching the [Release workflow](../.github/workflows/release.yml)
from the Actions tab. There are no API tokens anywhere: both indexes authenticate
the workflow through PyPI Trusted Publishing (OIDC), so nothing needs to be stored
in secrets and nothing needs to live on a developer machine.

Every release is rehearsed on TestPyPI first. The rehearsal is not optional
ceremony — an index will never let a version be replaced, only yanked, so a
mistake shipped to PyPI is permanent.

## Checklist

### 1. Prepare the bump

- [ ] **First release with the documentation site (0.3.0) only:** the release
      publishes `/latest/` for the first time, so repoint every `/dev/` docs link
      to `/latest/` in the same bump commit — `README.md`,
      `src/pytest_given/cli/report.py`, `src/pytest_given/plugin/options.py`, and
      `SKILL.md`, `references/api.md`, `references/scenarios.md` under
      `src/pytest_given/.agents/skills/pytest-given-authoring/`
      (`grep -rn "pytest-given/dev/"` finds them all, `AGENTS.md` included).
      Expect the TestPyPI rehearsal's link check (step 2) to 404 on those
      links — `/latest/` only exists once the `pypi` run has published it.
      Then delete this item.
- [ ] Bump `version` in `pyproject.toml`.
- [ ] Add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md`. The workflow
      extracts this exact section as the GitHub Release body, and fails the build
      if it is missing.
- [ ] Update the link references at the bottom of `CHANGELOG.md`: point
      `[Unreleased]` at the new tag, and add a line for the new version.
- [ ] Land it on `main` and wait for CI to go green. Releases can only be
      dispatched from `main`.

A PR is not required: `main` carries no branch protection and CI gates direct
pushes too, and the release workflow re-runs the whole gate in `verify` and
`build` before publishing anything, so a red `main` cannot produce a bad
release. A PR only buys running CI *before* the commit lands — worth it for
substantive changes, thin for a version bump.

No local `nox` run is listed here, on purpose: CI already runs the default gate
(minus `format`, which rewrites files where `lint`'s `ruff format --check`
already fails on the same drift) plus `nox -s build`, and the release workflow
then runs it again. The usual "run `uv run nox` before committing" rule from
[AGENTS.md](../AGENTS.md) applies to the bump commit like any other — it just
isn't a release-specific step. The exception is a change to packaging itself
(build config, the hatch include lists, anything affecting what lands in the
wheel): there `uv run nox -s build` locally is worth the faster loop, and it is
the only place a Windows-side packaging problem can surface at all, since CI is
Linux-only.

### 2. Rehearse on TestPyPI

- [ ] Actions → **Release** → Run workflow → target **`testpypi`**.
- [ ] `uv run nox -s check_release -- testpypi`
- [ ] Open <https://test.pypi.org/project/pytest-given/> and check the README
      renders, the diagram image loads, the links resolve, and the sidebar shows
      the four project URLs, the MIT license, and the right classifiers. This is
      the only place the rendered page can be checked before it is permanent.

`check_release` installs what the index actually serves into a throwaway
environment, runs a real scenario through it, and asserts the reports come out.
It deliberately runs from a temporary directory outside the project, so what it
imports is the published distribution and not `src/`. The awkward parts of doing
this by hand — resolving `pytest` and `jinja2` from real PyPI while
`pytest-given` comes from TestPyPI, allowing the `.dev` prerelease, and bypassing
uv's index cache so a rehearsal published moments ago is visible — are handled in
the session.

Rehearsals publish as `<version>.dev<run number>`, never the bare version, so the
same version can be re-rehearsed as many times as needed. The dev suffix sorts
*before* the release under PEP 440, so a rehearsal can never shadow the real
thing. Nothing is tagged.

### 3. Release to PyPI

- [ ] Actions → **Release** → Run workflow → target **`pypi`**.
- [ ] The `publish` job pauses for one minute — that is the wait timer on the
      `pypi` environment, not a hang.
- [ ] Confirm the run created the `v<version>` tag and a GitHub Release carrying
      the changelog section and both artifacts.
- [ ] `uv run nox -s check_release` — the same check as step 2, against real
      PyPI. Give the index a moment; a just-uploaded version can take a little
      while to appear.
- [ ] Confirm <https://nwilbert.github.io/pytest-given/latest/> resolves. If
      the `docs` job was cancelled by a concurrent push to `main` (the two
      share the `gh-pages` concurrency group), dispatch the Docs workflow with
      version `<major.minor>` and alias `latest`.

### 4. After

- [ ] Add a fresh empty `## [Unreleased]` section to `CHANGELOG.md`.

## Documentation site

The site at <https://nwilbert.github.io/pytest-given/> is built with Zensical and
published by [mike](https://github.com/squidfunk/mike) into the `gh-pages` branch:
`/dev/` on every push to `main` (the [Docs workflow](../.github/workflows/docs.yml)),
`/<major.minor>/` plus the `latest` alias by the `docs` job of the Release workflow
after a `pypi` release. The site root follows `latest` once a release has been
published, `dev` before that.

One-time setup, already done: **Settings → Pages → Build and deployment → Source:
Deploy from a branch → `gh-pages` / `(root)`**. If the site ever needs to be
republished by hand — a botched `gh-pages` commit, a moved alias — dispatch the
Docs workflow with the version and alias to publish; it runs the same
`nox -s docs_deploy` the automated paths use.

## What the workflow does

| job | runs | notes |
| --- | --- | --- |
| `verify` | `nox -s lint mypy test coverage audit` | Re-run rather than trusted from CI, because dispatch can target any ref. |
| `build` | guards, then `nox -s build` | Uploads `dist/` as a workflow artifact. |
| `publish` | `pypa/gh-action-pypi-publish` | Environment-scoped, `id-token: write`. |
| `github-release` | `gh release create` | Creates the `v<version>` tag and the GitHub Release. Skipped for rehearsals. |
| `docs` | `nox -s docs_deploy -- <major.minor> latest` | Publishes the release's docs as `/<major.minor>/` and moves the `latest` alias there. Skipped for rehearsals. |

The `build` job refuses to proceed if the tag already exists, if the version is
already on the target index, if `CHANGELOG.md` has no section for it, or — for
`pypi` — if the dispatch did not come from `main`.

**The `publish` job deliberately runs no project code.** It does not check out the
repository and does not run nox; it downloads the artifacts `build` already
verified and hands them to the publish action. Two reasons: the artifacts that get
uploaded are then provably the ones that passed the smoke test, and the one job
holding a credential that can publish under your name never executes your
dependency tree beside it.
