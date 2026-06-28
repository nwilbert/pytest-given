# Running pytest-given under WSL & Windows in parallel


## Why

Enable development under Windows with an IDE like PyCharm, while at the same time using a Linux sandbox for agentic development. But the venvs for Linux must not collide with the ones used for Windows.

So we keep the source on `/mnt/c`, but keep every virtual environment on the Linux filesystem (`/home/$USER/...`). The model is:

| Thing | Location | Filesystem |
| --- | --- | --- |
| Source / working tree | `/mnt/c/Users/Niko/repos/pytest-given` | Windows (9P mount) |
| `uv` project venv | `~/.local/share/uv-venvs/<project>` | Linux (ext4) |
| `nox` session venvs | `~/.local/share/nox-envs/<project>` | Linux (ext4) |

## The two redirections

`uv` and `nox` each create venvs, so each needs to be told where to put them.

### 1. `uv` — via `UV_PROJECT_ENVIRONMENT` in `.zshrc`

`uv` honours the `UV_PROJECT_ENVIRONMENT` environment variable to decide where a
project's `.venv` goes. We set it from a `chpwd` hook so it is populated
automatically whenever the shell enters a directory on the Windows mount, and
cleared elsewhere (so native-Linux projects keep their default in-repo `.venv`):

```zsh
function _set_uv_project_env() {
  if [[ "$PWD" == /mnt/* ]]; then
    export UV_PROJECT_ENVIRONMENT="/home/$USER/.local/share/uv-venvs/${PWD##*/}"
  else
    unset UV_PROJECT_ENVIRONMENT
  fi
}
autoload -Uz add-zsh-hook
add-zsh-hook chpwd _set_uv_project_env
_set_uv_project_env   # run once for the shell's starting directory
```

Notes:

- `${PWD##*/}` is the current directory's basename, so each project on `/mnt`
  gets its own venv directory keyed by folder name (e.g. `pytest-given`).
- The final bare call applies the rule to the directory the shell starts in;
  the `chpwd` hook covers every later `cd`.
- Because the variable is exported, every `uv sync` / `uv run` in this tree
  transparently creates and reuses the Linux-side venv — no per-command flags.

### 2. `nox` — via `nox.options.envdir` in `noxfile.py`

`nox` manages its own per-session venvs (`.nox/` by default, inside the repo)
and does not read `UV_PROJECT_ENVIRONMENT`. We redirect it at the top of
`noxfile.py`, gated so it only triggers under WSL on the Windows mount:

```python
from pathlib import Path
import nox

_proc_version = Path('/proc/version')
if (
    _proc_version.exists()
    and 'microsoft' in _proc_version.read_text().lower()
    and Path.cwd().is_relative_to('/mnt')
):
    nox.options.envdir = str(
        Path.home() / '.local' / 'share' / 'nox-envs' / 'pytest-given'
    )
```

The guard has three conditions, all of which must hold before the override
applies:

1. `/proc/version` exists, and
2. it mentions `microsoft` — i.e. we really are inside WSL, and
3. the working directory is under `/mnt` — i.e. the repo is on the Windows mount.

On a native Linux checkout (or macOS) none of this fires, so `nox` keeps its
default in-repo `.nox/` directory and the noxfile stays portable for anyone else.

## Source-path normalisation in `capture/source.py`

Running the same working tree from both Windows (PyCharm) and WSL has a second,
subtler consequence: the **paths Python records for source frames are not always
Linux paths**.

`capture/source.py` reconstructs a source location for `Story` and
`GlossaryTerm` objects from the call stack, turning each frame's
`co_filename` into a path relative to rootdir so the HTML report can render a
source link. On WSL, a frame for a file on the Windows mount can carry a
*Windows-style* `co_filename` (e.g. `C:\Users\Niko\repos\...`) rather than the
`/mnt/c/...` form. The trigger is the shared tree: a `.pyc` compiled by the
Windows interpreter caches the absolute Windows path, and once that path is
embedded in the code object the WSL interpreter sees it verbatim.

That breaks path handling, because `pathlib` on Linux treats `\` as an ordinary
filename character, not a separator. So `Path(r'C:\Users\Niko\repos\foo.py')` is
a *single-segment* relative path, `relative_to(rootdir)` raises `ValueError`,
and `capture_caller_source` silently returns `None` — the source link just
disappears from the report, with no error to explain why.

The fix is a small normalisation step applied before any `Path` math:
- Only a leading `<drive>:\` (matched by `_WINDOWS_PATH_RE`) is rewritten, and
  only when we are actually under WSL (`_IS_WSL`) — so a real Windows run of
  pytest, native Linux, and macOS are all left untouched.
- The drive letter is lowercased and the rest of the path has its backslashes
  flipped to forward slashes, producing the canonical `/mnt/c/...` mount path
  that lines up with rootdir.
- Plain Linux `co_filename`s fall straight through to `Path(filename)`, so this
  is a no-op everywhere except the Windows-path-under-WSL case.


