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

`uv` honors the `UV_PROJECT_ENVIRONMENT` environment variable to decide where a
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

## Source-path normalization in `capture/source.py`

`capture/source.py` reconstructs source locations (for `Story`/`GlossaryTerm`
frames, scenario `item.location`s, and glossary files) into paths relative to
rootdir so the HTML report can render source links. Running one working tree
from both sides has a second, subtler consequence for that: **a single file can
be recorded in either path convention, regardless of which interpreter is
running.** A `.pyc` compiled by one side caches its own absolute path, and the
other side reads it verbatim out of the code object — a Windows
`C:\Users\Niko\repos\...` under WSL, or a `/mnt/c/...` under native Windows.

Either way `relative_to(rootdir)` raises `ValueError`: Linux `pathlib` treats
`\` as an ordinary filename character, so the Windows path is a *single-segment
relative* one, while Windows `pathlib` reads a leading `/mnt/c/...` as
*drive-relative* and resolves it to a bogus `C:\mnt\c\...` sharing no drive
anchor with the real rootdir. `capture_caller_source` then silently returns
`None` and the source link just disappears from the report, with no error to
explain why.

The fix is a small bidirectional normalization, `_co_filename_to_path`, applied
before any `Path` math — both to captured `co_filename`s and, via
`set_rootdir`, to the rootdir itself, so the two sides always share an anchor.
Its docstring carries the rewrite table and the platform guards that keep it
inert on plain Linux and macOS.

Because the WSL `/mnt`-absolute assumption is POSIX-only, tests that assert it
must `skipif(sys.platform == 'win32', ...)`; every other test passes on all four
targets (native Windows, macOS, Linux, WSL).
