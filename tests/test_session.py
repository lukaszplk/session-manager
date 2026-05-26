"""Tests for SessionManager and SessionConfig.

Coverage:
  - SessionManager creation (directory, naming, base creation, uniqueness)
  - create=False — no folder created, latest() still works
  - separator shortcut and dataclasses.replace via _resolve_config
  - SessionConfig injection
  - Logger injection — messages routed through caller's logger
  - Path helpers (file, subdir, truediv)
  - Alternative constructor: in_temp()
  - Instance method: latest() with and without base_dir override
  - Repr
"""

import logging
import re
import time
from pathlib import Path

import pytest

from session_manager import SessionConfig, SessionManager
from session_manager.session import _resolve_config


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def base(tmp_path: Path) -> Path:
    return tmp_path / "results"


# ── _resolve_config ────────────────────────────────────────────────────────────

class TestResolveConfig:
    def test_all_none_returns_defaults(self) -> None:
        cfg = _resolve_config(None, None)
        assert cfg == SessionConfig()

    def test_separator_kwarg_overrides_config(self) -> None:
        base_cfg = SessionConfig(separator="_")
        cfg = _resolve_config(base_cfg, "--")
        assert cfg.separator == "--"
        assert cfg.timestamp_format == base_cfg.timestamp_format

    def test_separator_kwarg_overrides_default(self) -> None:
        cfg = _resolve_config(None, "--")
        assert cfg.separator == "--"

    def test_config_used_when_no_separator_kwarg(self) -> None:
        base_cfg = SessionConfig(separator="--", timestamp_format="%Y%m%d")
        cfg = _resolve_config(base_cfg, None)
        assert cfg is base_cfg

    def test_does_not_mutate_original_config(self) -> None:
        base_cfg = SessionConfig(separator="_")
        _resolve_config(base_cfg, "--")
        assert base_cfg.separator == "_"


# ── SessionManager creation ────────────────────────────────────────────────────

class TestSessionManagerCreation:
    def test_creates_session_dir(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.exists()
        assert sm.session_dir.is_dir()

    def test_session_dir_under_base(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.parent == base.resolve()

    def test_folder_name_contains_name_and_timestamp(self, base: Path) -> None:
        sm = SessionManager(base, name="analysis")
        assert re.match(r"^analysis_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$",
                        sm.session_dir.name)

    def test_no_name_uses_timestamp_only(self, base: Path) -> None:
        sm = SessionManager(base, name="")
        assert re.match(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$",
                        sm.session_dir.name)

    def test_creates_base_dir_if_missing(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        SessionManager(deep, name="run")
        assert deep.exists()

    def test_two_instances_get_different_dirs(self, base: Path) -> None:
        sm1 = SessionManager(base, name="run")
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        assert sm1.session_dir != sm2.session_dir

    def test_separator_kwarg_applied(self, base: Path) -> None:
        sm = SessionManager(base, name="run", separator="--")
        assert re.match(r"^run--\d{4}", sm.session_dir.name)

    def test_separator_kwarg_overrides_config(self, base: Path) -> None:
        cfg = SessionConfig(separator="_")
        sm = SessionManager(base, name="run", separator="--", config=cfg)
        assert sm.session_dir.name.startswith("run--")


# ── create=False ───────────────────────────────────────────────────────────────

class TestCreateFalse:
    def test_no_directory_created(self, base: Path) -> None:
        sm = SessionManager(base, name="run", create=False)
        assert not base.exists() or not any(base.iterdir())

    def test_session_dir_raises(self, base: Path) -> None:
        sm = SessionManager(base, name="run", create=False)
        with pytest.raises(RuntimeError, match="create=False"):
            _ = sm.session_dir

    def test_file_raises_via_session_dir(self, base: Path) -> None:
        sm = SessionManager(base, name="run", create=False)
        with pytest.raises(RuntimeError):
            sm.file("output.csv")

    def test_latest_works_without_own_session(self, base: Path) -> None:
        # writer
        writer = SessionManager(base, name="run")
        # reader — no folder of its own
        reader = SessionManager(base, name="run", create=False)
        assert reader.latest() == writer.session_dir


# ── Logger injection ───────────────────────────────────────────────────────────

class TestLoggerInjection:
    @pytest.fixture
    def logger_and_records(self):
        logger = logging.getLogger(f"test_{id(self)}")
        logger.setLevel(logging.DEBUG)
        records = []
        handler = logging.handlers_list = None

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Capture()
        logger.addHandler(handler)
        return logger, records

    def test_creation_logged(self, base: Path, logger_and_records) -> None:
        logger, records = logger_and_records
        SessionManager(base, name="run", logger=logger)
        assert any("created" in r.getMessage().lower() for r in records)

    def test_create_false_logged(self, base: Path, logger_and_records) -> None:
        logger, records = logger_and_records
        SessionManager(base, name="run", create=False, logger=logger)
        assert any("create=False" in r.getMessage() for r in records)

    def test_latest_scan_logged(self, base: Path, logger_and_records) -> None:
        logger, records = logger_and_records
        writer = SessionManager(base, name="run")
        reader = SessionManager(base, name="run", create=False, logger=logger)
        reader.latest()
        assert any("Scanning" in r.getMessage() for r in records)

    def test_no_logger_is_silent(self, base: Path) -> None:
        sm = SessionManager(base, name="run", logger=None)
        assert sm.session_dir.exists()


# ── SessionConfig injection ────────────────────────────────────────────────────

class TestSessionConfig:
    def test_custom_timestamp_format(self, base: Path) -> None:
        cfg = SessionConfig(timestamp_format="%Y%m%d")
        sm = SessionManager(base, name="run", config=cfg)
        assert re.match(r"^run_\d{8}$", sm.session_dir.name)

    def test_custom_separator(self, base: Path) -> None:
        cfg = SessionConfig(separator="--")
        sm = SessionManager(base, name="run", config=cfg)
        assert sm.session_dir.name.startswith("run--")

    def test_default_config_when_none(self, base: Path) -> None:
        sm = SessionManager(base, name="run", config=None)
        assert re.match(r"^run_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$",
                        sm.session_dir.name)


# ── Path helpers ───────────────────────────────────────────────────────────────

class TestPathHelpers:
    def test_file_returns_path_inside_session(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.file("output.csv").parent == sm.session_dir

    def test_file_accepts_multiple_parts(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.file("plots", "volcano.png") == sm.session_dir / "plots" / "volcano.png"

    def test_subdir_creates_directory(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        d = sm.subdir("plots")
        assert d.exists() and d.is_dir()

    def test_subdir_nested(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        d = sm.subdir("nested", "deep")
        assert d == sm.session_dir / "nested" / "deep"
        assert d.exists()

    def test_truediv_shorthand(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm / "file.txt" == sm.session_dir / "file.txt"


# ── in_temp ────────────────────────────────────────────────────────────────────

class TestInTemp:
    def test_creates_dir_in_system_temp(self) -> None:
        import tempfile
        sm = SessionManager.in_temp(name="tmp_run")
        assert str(sm.session_dir).startswith(
            str(Path(tempfile.gettempdir()).resolve()))

    def test_returns_session_manager(self) -> None:
        assert isinstance(SessionManager.in_temp(name="run"), SessionManager)

    def test_subclass_returns_subclass(self) -> None:
        class MySession(SessionManager):
            pass
        assert type(MySession.in_temp(name="sub")) is MySession

    def test_separator_kwarg_forwarded(self) -> None:
        sm = SessionManager.in_temp(name="run", separator="--")
        assert sm.session_dir.name.startswith("run--")


# ── latest() ──────────────────────────────────────────────────────────────────

class TestLatest:
    def test_returns_most_recent(self, base: Path) -> None:
        sm1 = SessionManager(base, name="run")
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        reader = SessionManager(base, name="run", create=False)
        assert reader.latest() == sm2.session_dir

    def test_filters_by_name(self, base: Path) -> None:
        sm_a = SessionManager(base, name="preprocess")
        time.sleep(1.1)
        SessionManager(base, name="train")
        reader = SessionManager(base, name="preprocess", create=False)
        assert reader.latest() == sm_a.session_dir

    def test_base_dir_override(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        sm_a = SessionManager(dir_a, name="run")
        reader = SessionManager(dir_b, name="run", create=False)
        assert reader.latest(base_dir=dir_a) == sm_a.session_dir

    def test_raises_if_dir_missing(self, tmp_path: Path) -> None:
        reader = SessionManager(tmp_path / "missing", name="run", create=False)
        with pytest.raises(FileNotFoundError):
            reader.latest()

    def test_raises_if_no_sessions(self, base: Path) -> None:
        base.mkdir(parents=True)
        reader = SessionManager(base, name="run", create=False)
        with pytest.raises(ValueError):
            reader.latest()

    def test_separator_ambiguity_avoided(self, base: Path) -> None:
        sm_run = SessionManager(base, name="run")
        time.sleep(1.1)
        SessionManager(base, name="run_extra")
        reader = SessionManager(base, name="run", create=False)
        assert reader.latest() == sm_run.session_dir

    def test_custom_separator_exact_match(self, base: Path) -> None:
        sm = SessionManager(base, name="preprocess", separator="--")
        reader = SessionManager(base, name="preprocess",
                                separator="--", create=False)
        assert reader.latest() == sm.session_dir

    def test_accepts_string_base_dir_override(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        reader = SessionManager(base, name="run", create=False)
        assert reader.latest(base_dir=str(base)) == sm.session_dir


# ── Repr ───────────────────────────────────────────────────────────────────────

class TestRepr:
    def test_contains_class_name(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert "SessionManager" in repr(sm)

    def test_contains_session_folder_name(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.name in repr(sm)

    def test_contains_name(self, base: Path) -> None:
        sm = SessionManager(base, name="myrun")
        assert "myrun" in repr(sm)
