# Releasing pytest-given to PyPI

Releases are cut by manually dispatching the [Release workflow](../.github/workflows/release.yml)
from the Actions tab. There are no API tokens anywhere: both indexes authenticate
the workflow through PyPI Trusted Publishing (OIDC), so nothing needs to be stored
in secrets and nothing needs to live on a developer machine.

Every release is rehearsed on TestPyPI first. The rehearsal is not optional
ceremony — an index will never let a version be replaced, only yanked, so a
mistake shipped to PyPI is permanent.

## Checklist

### 1. Prepare the bump (in a PR)

- [ ] Bump `version` in `pyproject.toml`.
- [ ] Add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md`. The workflow
      extracts this exact section as the GitHub Release body, and fails the build
      if it is missing.
- [ ] Update the link references at the bottom of `CHANGELOG.md`: point
      `[Unreleased]` at the new tag, and add a line for the new version.
- [ ] Merge to `main` once CI is green. Releases can only be dispatched from
      `main`.

No local `nox` run is listed here, on purpose. The bump PR is already gated by
CI, whose `quality`, `test`, `package` and `audit` jobs cover the full six-session
gate plus `nox -s build`; the release workflow then runs the same set again in
`verify` and `build` before anything is published. A local run before dispatching
would be the third. The usual "run `uv run nox` before committing" rule from
[AGENTS.md](../AGENTS.md) applies to the bump commit like any other — it just
isn't a release-specific step.

The exception is a change to packaging itself: build config in `pyproject.toml`,
the hatch include lists, or anything affecting what lands in the wheel. There
`uv run nox -s build` locally is worth it for the faster loop, and it is the only
place a Windows-side packaging problem can surface at all, since CI is
Linux-only.

### 2. Rehearse on TestPyPI

- [ ] Actions → **Release** → Run workflow → target **`testpypi`**.
- [ ] Install the published wheel with the script below and open the report it
      writes to `given-report/report.html`.
- [ ] Open <https://test.pypi.org/project/pytest-given/> and check the README
      renders, the diagram image loads, the links resolve, and the sidebar shows
      the four project URLs, the MIT license, and the right classifiers. This is
      the only place the rendered page can be checked before it is permanent.

```bash
mkdir -p /tmp/pg-smoke && cd /tmp/pg-smoke
cat > test_smoke.py <<'EOF'
from pytest_given import given, scenario, then, when

@scenario('Installing from TestPyPI works')
def test_smoke():
    with given('the published wheel'):
        installed = True
    with then('narration is captured'):
        assert installed
EOF
uv run --isolated --no-project \
  --index https://test.pypi.org/simple/ \
  --index-strategy unsafe-best-match \
  --prerelease allow \
  --with pytest-given pytest test_smoke.py --given-html
```

Three details in that command are load-bearing. The empty directory matters — run
it inside a tree containing other projects and pytest will try to collect them.
`--index-strategy unsafe-best-match` is needed because `pytest` and `jinja2` must
still come from real PyPI while `pytest-given` comes from TestPyPI. And
`--prerelease allow` is needed because rehearsals publish `.dev` versions, which
are not installed by default.

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
- [ ] Install from real PyPI and smoke it, same as step 2 without the `--index`,
      `--index-strategy` and `--prerelease` flags.

### 4. After

- [ ] Add a fresh empty `## [Unreleased]` section to `CHANGELOG.md`.

## What the workflow does

| job | runs | notes |
| --- | --- | --- |
| `verify` | `nox -s lint format mypy test coverage audit` | Re-run rather than trusted from CI, because dispatch can target any ref. |
| `build` | guards, then `nox -s build` | Uploads `dist/` as a workflow artifact. |
| `publish` | `pypa/gh-action-pypi-publish` | Environment-scoped, `id-token: write`. |
| `release` | `gh release create` | Skipped for rehearsals. Creates the tag. |

The `build` job refuses to proceed if the tag already exists, if the version is
already on the target index, if `CHANGELOG.md` has no section for it, or — for
`pypi` — if the dispatch did not come from `main`.

**The `publish` job deliberately runs no project code.** It does not check out the
repository and does not run nox; it downloads the artifacts `build` already
verified and hands them to the publish action. Two reasons: the artifacts that get
uploaded are then provably the ones that passed the smoke test, and the one job
holding a credential that can publish under your name never executes your
dependency tree beside it.

## Troubleshooting

| symptom | cause |
| --- | --- |
| `tag v<x> already exists` | That version was already released. Bump it. |
| `pytest-given <x> is already on <index>` | Same — a version can never be replaced, only yanked. |
| `CHANGELOG.md has no '## [x]' section` | Add the section; the release body comes from it. |
| `pypi releases must be dispatched from main` | Re-dispatch from `main`. |
| `403` from the index in `publish` | The trusted publisher's fields do not match reality. All four must agree: owner `nwilbert`, repo `pytest-given`, workflow `release.yml`, environment `pypi` / `testpypi`. |
| `publish` sits idle for a minute | The wait timer on the `pypi` environment. |
| Rehearsal install resolves nothing | Rehearsals are `.dev` versions; add `--prerelease allow` or pin the exact version. |

## One-time setup (already done)

Recorded so it is not mysterious later, and so it can be recreated if the repo
moves.

**On pypi.org and test.pypi.org** — Account settings → Publishing → *pending
publisher*. "Pending" is the mechanism for claiming a name that does not exist on
the index yet; it converts to an ordinary trusted publisher on first upload.

| field | value |
| --- | --- |
| PyPI Project Name | `pytest-given` |
| Owner | `nwilbert` — the **GitHub** owner, not the PyPI username |
| Repository name | `pytest-given` |
| Workflow name | `release.yml` |
| Environment name | `pypi` / `testpypi` |

**On GitHub** — Settings → Environments → `pypi` and `testpypi`. No secrets or
variables; the environments exist so PyPI can verify the name as part of the OIDC
claim, and so `pypi` can carry protection rules.

`pypi` restricts deployments to `main`. That rule — not the workflow's own
"Require main" step — is the one that actually holds: `workflow_dispatch` runs the
workflow file *from the ref it is dispatched on*, so an in-workflow check can be
edited away on a branch, while an environment rule lives in repo settings and
cannot.
