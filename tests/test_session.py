"""Tests for SessionManager."""

import logging
import re
import time
from pathlib import Path

import pytest

from session_manager import SessionManager


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def base(tmp_path: Path) -> Path:
    return tmp_path / "results"


@pytest.fixture
def logger_and_records():
    logger = logging.getLogger(f"test_{id(logger_and_records)}")
    logger.setLevel(logging.DEBUG)
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger.addHandler(Capture())
    return logger, records


# ── Creation ───────────────────────────────────────────────────────────────────

class TestCreation:
    def test_creates_session_dir(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.exists() and sm.session_dir.is_dir()

    def test_session_dir_under_base(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.parent == base.resolve()

    def test_default_folder_name_format(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert re.match(r"^run_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$",
                        sm.session_dir.name)

    def test_empty_name_uses_timestamp_only(self, base: Path) -> None:
        sm = SessionManager(base, name="")
        assert re.match(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$",
                        sm.session_dir.name)

    def test_creates_missing_base_dir(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        SessionManager(deep, name="run")
        assert deep.exists()

    def test_two_instances_differ(self, base: Path) -> None:
        sm1 = SessionManager(base, name="run")
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        assert sm1.session_dir != sm2.session_dir

    def test_custom_separator(self, base: Path) -> None:
        sm = SessionManager(base, name="run", separator="--")
        assert re.match(r"^run--\d{4}", sm.session_dir.name)

    def test_custom_timestamp_format(self, base: Path) -> None:
        sm = SessionManager(base, name="run", timestamp_format="%Y%m%d")
        assert re.match(r"^run_\d{8}$", sm.session_dir.name)


# ── create=False ───────────────────────────────────────────────────────────────

class TestCreateFalse:
    def test_no_directory_created(self, base: Path) -> None:
        SessionManager(base, name="run", create=False)
        assert not base.exists() or not any(base.iterdir())

    def test_session_dir_raises(self, base: Path) -> None:
        sm = SessionManager(base, name="run", create=False)
        with pytest.raises(RuntimeError, match="create=False"):
            _ = sm.session_dir

    def test_file_raises(self, base: Path) -> None:
        sm = SessionManager(base, name="run", create=False)
        with pytest.raises(RuntimeError):
            sm.file("output.csv")

    def test_latest_works_without_own_session(self, base: Path) -> None:
        writer = SessionManager(base, name="run")
        reader = SessionManager(base, name="run", create=False)
        assert reader.latest() == writer.session_dir


# ── Logger injection ───────────────────────────────────────────────────────────

class TestLogger:
    def _make_logger(self):
        logger = logging.getLogger(f"test_{id(self)}_{time.time()}")
        logger.setLevel(logging.DEBUG)
        records = []

        class Capture(logging.Handler):
            def emit(self, r):
                records.append(r)

        logger.addHandler(Capture())
        return logger, records

    def test_creation_emits_debug(self, base: Path) -> None:
        logger, records = self._make_logger()
        SessionManager(base, name="run", logger=logger)
        assert any("created" in r.getMessage().lower() for r in records)

    def test_create_false_emits_debug(self, base: Path) -> None:
        logger, records = self._make_logger()
        SessionManager(base, name="run", create=False, logger=logger)
        assert any("create=False" in r.getMessage() for r in records)

    def test_latest_emits_scan_log(self, base: Path) -> None:
        logger, records = self._make_logger()
        SessionManager(base, name="run")
        reader = SessionManager(base, name="run", create=False, logger=logger)
        reader.latest()
        assert any("Scanning" in r.getMessage() for r in records)

    def test_none_logger_is_silent(self, base: Path) -> None:
        sm = SessionManager(base, name="run", logger=None)
        assert sm.session_dir.exists()


# ── Path helpers ───────────────────────────────────────────────────────────────

class TestPathHelpers:
    def test_file_inside_session(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.file("output.csv").parent == sm.session_dir

    def test_file_multiple_parts(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.file("plots", "fig.png") == sm.session_dir / "plots" / "fig.png"

    def test_subdir_created(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        d = sm.subdir("plots")
        assert d.exists() and d.is_dir()

    def test_subdir_nested(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        d = sm.subdir("a", "b")
        assert d == sm.session_dir / "a" / "b" and d.exists()

    def test_truediv(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm / "f.txt" == sm.session_dir / "f.txt"


# ── in_temp ────────────────────────────────────────────────────────────────────

class TestInTemp:
    def test_creates_in_system_temp(self) -> None:
        import tempfile
        sm = SessionManager.in_temp(name="run")
        assert str(sm.session_dir).startswith(
            str(Path(tempfile.gettempdir()).resolve()))

    def test_returns_session_manager(self) -> None:
        assert isinstance(SessionManager.in_temp(), SessionManager)

    def test_subclass_returns_subclass(self) -> None:
        class MySession(SessionManager):
            pass
        assert type(MySession.in_temp()) is MySession

    def test_separator_forwarded(self) -> None:
        sm = SessionManager.in_temp(name="run", separator="--")
        assert sm.session_dir.name.startswith("run--")


# ── latest() ──────────────────────────────────────────────────────────────────

class TestLatest:
    def test_returns_most_recent(self, base: Path) -> None:
        SessionManager(base, name="run")
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
        dir_a, dir_b = tmp_path / "a", tmp_path / "b"
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

    def test_no_prefix_ambiguity(self, base: Path) -> None:
        sm_run = SessionManager(base, name="run")
        time.sleep(1.1)
        SessionManager(base, name="run_extra")
        reader = SessionManager(base, name="run", create=False)
        assert reader.latest() == sm_run.session_dir

    def test_custom_separator_matched(self, base: Path) -> None:
        sm = SessionManager(base, name="run", separator="--")
        reader = SessionManager(base, name="run", separator="--", create=False)
        assert reader.latest() == sm.session_dir

    def test_accepts_string_base_dir(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        reader = SessionManager(base, name="run", create=False)
        assert reader.latest(base_dir=str(base)) == sm.session_dir


# ── Repr ───────────────────────────────────────────────────────────────────────

class TestRepr:
    def test_contains_class_name(self, base: Path) -> None:
        assert "SessionManager" in repr(SessionManager(base, name="run"))

    def test_contains_folder_name(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.name in repr(sm)

    def test_contains_name(self, base: Path) -> None:
        sm = SessionManager(base, name="myrun")
        assert "myrun" in repr(sm)
