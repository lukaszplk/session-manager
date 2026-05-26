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

# start a new session — folder created immediately
sm = SessionManager("results", name="rna_seq")
# → results/rna_seq_2026-05-26_22-08-00/

df.to_csv(sm.file("counts.csv"))
fig.savefig(sm.file("volcano.png"))
plots = sm.subdir("plots")        # creates subdir, returns Path
fig2.savefig(plots / "pca.png")
fig3.savefig(sm / "overview.png") # shorthand
```

## Pipeline chaining

```python
# script_a.py — runs multiple times
sm = SessionManager("results", name="preprocess")
df_clean.to_csv(sm.file("clean.csv"))

# script_b.py — always picks up script A's latest output
sm = SessionManager("results", name="preprocess", create=False)
latest = sm.latest()
logger.info("Using session: %s", latest)   # log at script level
df = pd.read_csv(latest / "clean.csv")

# scan a different folder
latest = sm.latest(base_dir="other/results")
```

## Logger injection

Pass your application logger so the library's internal events flow through
your handlers, formatters, and custom levels — all in one log file.

```python
sm = SessionManager("results", name="rna_seq", logger=logger)
# library emits: logger.debug("Session created: results/rna_seq_2026-...")
```

`None` (default) is silent — the library never configures its own handlers.

## Temp directory

`in_temp` is a convenience constructor — identical to passing
`Path(tempfile.gettempdir())` as `base_dir`, without needing to import
`tempfile` or know the OS-specific temp path.

```python
sm = SessionManager.in_temp(name="scratch")
# → /tmp/scratch_2026-05-26_21-57-00/   (Linux/macOS)
# → %TEMP%\scratch_2026-05-26_21-57-00\ (Windows)
```

## Custom config

Three levels — use only as much as you need:

```python
from session_manager import SessionManager, SessionConfig

# level 1 — zero config
sm = SessionManager("results", name="run")

# level 2 — tweak one thing inline, no extra import
sm = SessionManager("results", name="run", separator="--")

# level 3 — full control, reusable across writer and reader
cfg = SessionConfig(timestamp_format="%Y%m%dT%H%M%S", separator="--")
sm     = SessionManager("results", name="run", config=cfg)
latest = sm_reader.latest()         # picks up the same separator automatically
```

### Separator-aware matching

When a `config` or `separator` is set, `latest()` uses `name--\d` regex
matching — so `"run"` never accidentally matches `"run_extra_..."`.
Without them, it falls back to a plain `startswith`.

## API

### `SessionConfig`

| Field | Default | Description |
|---|---|---|
| `timestamp_format` | `"%Y-%m-%d_%H-%M-%S"` | `strftime` format for the timestamp |
| `separator` | `"_"` | String between *name* and timestamp |

### `SessionManager(base_dir, name="session", *, separator, config, create, logger)`

| Argument | Default | Description |
|---|---|---|
| `base_dir` | required | Parent directory for sessions |
| `name` | `"session"` | Folder name prefix |
| `separator` | `None` | Quick separator override (takes precedence over `config`) |
| `config` | `None` | Full `SessionConfig` object |
| `create` | `True` | `False` = configured object only, no folder created |
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
