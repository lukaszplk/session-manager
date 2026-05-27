# session-manager

[![CI](https://github.com/lukaszplk/session-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/lukaszplk/session-manager/actions/workflows/ci.yml)
[![Release](https://github.com/lukaszplk/session-manager/actions/workflows/release.yml/badge.svg)](https://github.com/lukaszplk/session-manager/actions/workflows/release.yml)

Lightweight timestamped session-directory manager for data-processing scripts.

Each time your script runs it gets its own uniquely named folder — no overwritten results, no manual date-stamping. Works on Windows and Linux (`pathlib.Path` throughout).

## Install

```bash
pip install session-manager

# always latest from GitHub
pip install git+https://github.com/lukaszplk/session-manager.git
```

---

## Use cases

### 1. Save outputs from a data-processing script

Every run produces a fresh folder. Re-run as many times as you like — nothing gets overwritten.

```python
from session_manager import SessionManager

sm = SessionManager("results", name="rna_seq")
# creates: results/rna_seq_2026-05-27_20-00-00/

df.to_csv(sm.file("counts.csv"))
fig.savefig(sm.file("volcano.png"))

plots = sm.subdir("plots")        # creates subdir, returns Path
fig2.savefig(plots / "pca.png")
fig3.savefig(sm / "overview.png") # shorthand
```

### 2. Zero-config — bare constructor

No path to decide? Let the library choose:

```python
sm = SessionManager()
# creates: ./sm-sessions/session_2026-05-27_20-00-00/
```

### 3. Pipeline chaining — script B always picks up script A's latest output

```python
# script_a.py
sm = SessionManager("results", name="preprocess")
sm.save_params({"lr": 0.01, "epochs": 50})  # writes params.json
df_clean.to_csv(sm.file("clean.csv"))
```

```python
# script_b.py
sm = SessionManager("results", name="preprocess", create=False)
latest = sm.latest()
df = pd.read_csv(latest / "clean.csv")
```

### 4. Browse all past runs

```python
sm = SessionManager("results", name="run", create=False)
for session in sm.list_sessions():           # oldest → newest
    print(session.name)
```

### 5. Auto-archive old sessions

Keep the last N sessions active; older ones are moved to an archive folder automatically on each new run:

```python
sm = SessionManager("results", name="run", max_sessions=5)
# once you have 5 sessions, the oldest is moved to results/archive/
# custom archive location:
sm = SessionManager("results", name="run", max_sessions=5, archive_dir="old_runs")
```

### 6. Stable symlink for downstream scripts

```python
sm = SessionManager("results", name="run")
sm.symlink_latest()
# creates/updates results/latest → current session
# downstream scripts always read from results/latest/ without calling latest()
```

> **Note:** On Windows, symlinks require Developer Mode or elevated privileges.

### 7. Save parameters and environment

```python
sm = SessionManager("results", name="run")
sm.save_params({"lr": 0.01, "dropout": 0.3, "model": "resnet50"})
# → params.json (pretty-printed, non-serialisable values fall back to str)

sm.save_env()
# → environment.txt (pip freeze output for full reproducibility)

# custom filenames
sm.save_params(cfg, filename="config.json")
sm.save_env(filename="requirements.txt")
```

### 8. Logger injection — all output in one place

```python
import logging
from session_manager import SessionManager

logger = logging.getLogger("my_pipeline")
sm = SessionManager("results", name="rna_seq", logger=logger)
logger.info("Processing %d samples", len(df))
# library events and your logs share the same handlers/formatters
```

### 9. Scratch / temp work

```python
sm = SessionManager.in_temp(name="scratch")
# → /tmp/scratch_2026-05-27_20-00-00/   (Linux/macOS)
# → %TEMP%\scratch_2026-05-27_20-00-00\ (Windows)
```

### 10. Experiment tracking

```python
for lr in [0.001, 0.01, 0.1]:
    sm = SessionManager("experiments", name=f"lr_{lr}")
    sm.save_params({"lr": lr})
    model.fit(X_train, y_train, lr=lr)
    json.dump(evaluate(model, X_test), open(sm.file("metrics.json"), "w"))
```

---

## Options

```python
sm = SessionManager(
    "results",            # omit to use ./sm-sessions/ in cwd
    name="run",
    separator="--",                    # default "_"
    timestamp_format="%Y%m%dT%H%M%S", # default "%Y-%m-%d_%H-%M-%S"
    create=False,                      # default True
    max_sessions=5,                    # default None (no archiving)
    archive_dir="old_runs",            # default base_dir/archive/
    logger=logger,                     # default None (silent)
)
```

---

## API

### Constructor

| Argument | Default | Description |
|---|---|---|
| `base_dir` | `./sm-sessions/` | Parent directory for sessions |
| `name` | `"session"` | Folder name prefix |
| `separator` | `"_"` | Between name and timestamp |
| `timestamp_format` | `"%Y-%m-%d_%H-%M-%S"` | `strftime` format |
| `create` | `True` | `False` = no folder created (use with `latest()` / `list_sessions()`) |
| `max_sessions` | `None` | Auto-archive oldest folders when limit is reached |
| `archive_dir` | `base_dir/archive/` | Destination for archived sessions |
| `logger` | `None` | `logging.Logger` for internal events |

### Methods & properties

| Method / property | Returns | Description |
|---|---|---|
| `session_dir` | `Path` | Session root (raises if `create=False`) |
| `file(*parts)` | `Path` | Path inside session dir (not created) |
| `subdir(*parts)` | `Path` | Subdirectory (created immediately) |
| `sm / "name"` | `Path` | Shorthand for `session_dir / name` |
| `latest(base_dir=None)` | `Path` | Most recent matching session folder |
| `list_sessions(base_dir=None)` | `list[Path]` | All matching sessions, oldest first |
| `symlink_latest(name="latest")` | `Path` | Create/update `base_dir/latest` symlink |
| `save_params(data, filename="params.json")` | `Path` | Serialise dict as pretty JSON |
| `save_env(filename="environment.txt")` | `Path` | Save `pip freeze` output |
| `SessionManager.in_temp(name, ...)` | `SessionManager` | Constructor using system temp dir |

---

## Development

```bash
git clone https://github.com/lukaszplk/session-manager.git
cd session-manager
pip install -e ".[dev]"
pytest
```

Work on a feature branch, open a PR against `master` — CI runs automatically on the PR.
