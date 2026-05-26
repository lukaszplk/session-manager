# session-manager

[![CI](https://github.com/lukaszplk/session-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/lukaszplk/session-manager/actions/workflows/ci.yml)
[![Release](https://github.com/lukaszplk/session-manager/actions/workflows/release.yml/badge.svg)](https://github.com/lukaszplk/session-manager/actions/workflows/release.yml)

Lightweight timestamped session-directory manager for data-processing scripts.

Each time your script runs it gets its own uniquely named folder — no overwritten results, no manual date-stamping. Works on Windows and Linux (`pathlib.Path` throughout).

## Install

```bash
# from PyPI (after first release)
pip install session-manager

# directly from GitHub (always latest)
pip install git+https://github.com/lukaszplk/session-manager.git
```

---

## Use cases

### 1. Save outputs from a data-processing script

Every run produces a fresh folder. Re-run as many times as you like — nothing gets overwritten.

```python
from session_manager import SessionManager

sm = SessionManager("results", name="rna_seq")
# creates: results/rna_seq_2026-05-26_22-08-00/

df.to_csv(sm.file("counts.csv"))
fig.savefig(sm.file("volcano.png"))

plots = sm.subdir("plots")        # creates subdir, returns Path
fig2.savefig(plots / "pca.png")
fig3.savefig(sm / "overview.png") # shorthand
```

Resulting folder:
```
results/
└── rna_seq_2026-05-26_22-08-00/
    ├── counts.csv
    ├── volcano.png
    └── plots/
        └── pca.png
```

---

### 2. Pipeline chaining — script B always picks up script A's latest output

No hardcoded paths, no manual coordination between scripts.

```python
# script_a.py  (preprocessing — run multiple times during development)
from session_manager import SessionManager

sm = SessionManager("results", name="preprocess")
df_clean.to_csv(sm.file("clean.csv"))
model_params = {"lr": 0.01, "epochs": 50}
json.dump(model_params, open(sm.file("params.json"), "w"))
```

```python
# script_b.py  (training — always reads A's latest output)
from session_manager import SessionManager

sm = SessionManager("results", name="preprocess", create=False)
latest = sm.latest()

logger.info("Reading from: %s", latest)
df = pd.read_csv(latest / "clean.csv")
params = json.load(open(latest / "params.json"))
```

---

### 3. Logger injection — all output in one place

Pass your application logger so the library's events (folder created, scan
results, errors) flow through your handlers, formatters, and custom levels.

```python
import logging
from session_manager import SessionManager

logger = logging.getLogger("my_pipeline")
sm = SessionManager("results", name="rna_seq", logger=logger)
# → logger.debug("Session created: results/rna_seq_2026-...")

# library logs and your script logs end up in the same file
logger.info("Processing %d samples", len(df))
```

---

### 4. Scratch / temp work

For intermediate results that don't need to persist, use the system temp
directory — no path to decide, works the same on Windows and Linux.

```python
from session_manager import SessionManager

sm = SessionManager.in_temp(name="scratch")
# → /tmp/scratch_2026-05-26_22-08-00/    (Linux/macOS)
# → %TEMP%\scratch_2026-05-26_22-08-00\  (Windows)

large_intermediate_df.to_parquet(sm.file("intermediate.parquet"))
```

---

### 5. Experiment tracking

Keep every hyperparameter sweep run isolated and comparable.

```python
for lr in [0.001, 0.01, 0.1]:
    sm = SessionManager("experiments", name=f"lr_{lr}")
    model.fit(X_train, y_train, lr=lr)
    metrics = evaluate(model, X_test, y_test)
    json.dump(metrics, open(sm.file("metrics.json"), "w"))
    model.save(sm.file("model.pt"))
```

Resulting folder:
```
experiments/
├── lr_0.001_2026-05-26_22-10-00/
│   ├── metrics.json
│   └── model.pt
├── lr_0.01_2026-05-26_22-10-05/
│   ├── metrics.json
│   └── model.pt
└── lr_0.1_2026-05-26_22-10-10/
    ├── metrics.json
    └── model.pt
```

---

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

---

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

---

## Development

```bash
git clone https://github.com/lukaszplk/session-manager.git
cd session-manager
pip install -e ".[dev]"
pytest
```

Work on a feature branch, open a PR against `master` — CI runs automatically on the PR.

