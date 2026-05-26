# session-manager

[![CI](https://github.com/lukaszplk/session-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/lukaszplk/session-manager/actions/workflows/ci.yml)

Lightweight timestamped session-directory manager for data-processing scripts.

Each time your script runs it gets its own uniquely named folder — no overwritten results, no manual date-stamping.

## Install

```bash
pip install git+https://github.com/lukaszplk/session-manager.git
```

## Quick start

```python
from session_manager import SessionManager

sm = SessionManager("results", name="rna_seq")
# creates:  results/rna_seq_2026-05-26_21-57-00/

df.to_csv(sm.file("counts.csv"))
fig.savefig(sm.file("volcano.png"))

plots_dir = sm.subdir("plots")      # creates the subdir and returns the Path
fig2.savefig(plots_dir / "pca.png")

# shorthand
fig3.savefig(sm / "overview.png")
```

Works on Windows and Linux — all paths are `pathlib.Path` objects.

## Temp directory

```python
sm = SessionManager.in_temp(name="scratch")
# creates:  /tmp/scratch_2026-05-26_21-57-00/   (Linux/macOS)
#        or %TEMP%\scratch_2026-05-26_21-57-00\ (Windows)
```

## Pipeline chaining — always pick the latest session

```python
# script_a.py — runs multiple times, each run creates a new session
sm = SessionManager("results", name="preprocess")
df_clean.to_csv(sm.file("clean.csv"))

# script_b.py — always picks up the most recent preprocess session
latest = SessionManager.latest("results", name="preprocess")
df = pd.read_csv(latest / "clean.csv")
```

## Custom config

```python
from session_manager import SessionManager, SessionConfig

cfg = SessionConfig(
    timestamp_format="%Y%m%dT%H%M%S",
    separator="--",
)
sm = SessionManager("results", name="run", config=cfg)
# creates:  results/run--20260526T215700/
```

## API

### `SessionConfig`

| Field | Default | Description |
|---|---|---|
| `timestamp_format` | `"%Y-%m-%d_%H-%M-%S"` | `strftime` format for the timestamp part |
| `separator` | `"_"` | String placed between *name* and timestamp |

### `SessionManager(base_dir, name="session", config=None)`

| Method / property | Returns | Description |
|---|---|---|
| `session_dir` | `Path` | Absolute path to the session root |
| `file(*parts)` | `Path` | Path inside the session dir (not created) |
| `subdir(*parts)` | `Path` | Subdirectory inside the session dir (created) |
| `sm / "name"` | `Path` | Shorthand for `sm.file("name")` |
| `SessionManager.in_temp(name, config)` | `SessionManager` | Alternative constructor using the system temp dir |
| `SessionManager.latest(sessions_dir, name)` | `Path` | Path to the most recently created session folder |

## Run tests

```bash
pip install pytest
pytest
```
