# session-manager

[![CI](https://github.com/lukaszplk/session-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/lukaszplk/session-manager/actions/workflows/ci.yml)

Lightweight timestamped session-directory manager for data-processing scripts.

Each time your script runs it gets its own uniquely named folder — no overwritten results, no manual date-stamping. Works on Windows and Linux (`pathlib.Path` throughout).

## Install

```bash
pip install git+https://github.com/lukaszplk/session-manager.git
```

## Quick start

```python
from session_manager import SessionManager

sm = SessionManager("results", name="rna_seq")
# → results/rna_seq_2026-05-26_22-08-00/

df.to_csv(sm.file("counts.csv"))
fig.savefig(sm.file("volcano.png"))
plots = sm.subdir("plots")         # creates subdir, returns Path
fig2.savefig(plots / "pca.png")
fig3.savefig(sm / "overview.png")  # shorthand
```

## Pipeline chaining

```python
# script_a.py — runs multiple times, each run creates a new session
sm = SessionManager("results", name="preprocess")
df_clean.to_csv(sm.file("clean.csv"))

# script_b.py — always picks up script A's latest output, no folder created
sm = SessionManager("results", name="preprocess", create=False)
latest = sm.latest()
logger.info("Using session: %s", latest)
df = pd.read_csv(latest / "clean.csv")

# scan a different folder
latest = sm.latest(base_dir="other/results")
```

## Logger injection

Pass your application logger so the library's internal events (folder
created, scan results, errors) flow through your handlers and formatters.

```python
sm = SessionManager("results", name="rna_seq", logger=logger)
# → logger.debug("Session created: results/rna_seq_2026-...")
```

`None` (default) is fully silent.

## Temp directory

```python
sm = SessionManager.in_temp(name="scratch")
# → /tmp/scratch_2026-05-26_22-08-00/   (Linux/macOS)
# → %TEMP%\scratch_2026-05-26_22-08-00\ (Windows)
```

## Options

All optional, all keyword-only:

```python
sm = SessionManager(
    "results",
    name="run",
    separator="--",                    # default "_"
    timestamp_format="%Y%m%dT%H%M%S", # default "%Y-%m-%d_%H-%M-%S"
    create=False,                      # default True
    logger=logger,                     # default None (silent)
)
```

## API

### `SessionManager(base_dir, name="session", *, separator, timestamp_format, create, logger)`

| Argument | Default | Description |
|---|---|---|
| `base_dir` | required | Parent directory for sessions |
| `name` | `"session"` | Folder name prefix |
| `separator` | `"_"` | Between name and timestamp |
| `timestamp_format` | `"%Y-%m-%d_%H-%M-%S"` | `strftime` format |
| `create` | `True` | `False` = no folder created (use with `latest()`) |
| `logger` | `None` | `logging.Logger` for internal events |

| Method / property | Returns | Description |
|---|---|---|
| `session_dir` | `Path` | Session root (raises if `create=False`) |
| `file(*parts)` | `Path` | Path inside session dir (not created) |
| `subdir(*parts)` | `Path` | Subdirectory (created) |
| `sm / "name"` | `Path` | Shorthand for `session_dir / name` |
| `latest(base_dir=None)` | `Path` | Latest matching session folder |
| `SessionManager.in_temp(name, ...)` | `SessionManager` | Constructor using system temp dir |

## Run tests

```bash
pip install pytest
pytest
```
