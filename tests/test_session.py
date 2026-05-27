"""Tests for SessionManager."""

import json
import logging
import re
import sys
import time
from datetime import datetime
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


# ── Bare constructor ───────────────────────────────────────────────────────────

class TestBareConstructor:
    def test_no_args_creates_sm_sessions(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        sm = SessionManager()
        assert sm.session_dir.parent == tmp_path / "sm-sessions"

    def test_no_args_session_dir_exists(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        sm = SessionManager()
        assert sm.session_dir.exists()


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


# ── list_sessions ─────────────────────────────────────────────────────────────

class TestListSessions:
    def test_empty_returns_empty_list(self, base: Path) -> None:
        base.mkdir(parents=True)
        sm = SessionManager(base, name="run", create=False)
        assert sm.list_sessions() == []

    def test_missing_dir_returns_empty_list(self, base: Path) -> None:
        sm = SessionManager(base, name="run", create=False)
        assert sm.list_sessions() == []

    def test_returns_all_sessions(self, base: Path) -> None:
        sm1 = SessionManager(base, name="run")
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        reader = SessionManager(base, name="run", create=False)
        assert reader.list_sessions() == [sm1.session_dir, sm2.session_dir]

    def test_oldest_first(self, base: Path) -> None:
        sm1 = SessionManager(base, name="run")
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        reader = SessionManager(base, name="run", create=False)
        sessions = reader.list_sessions()
        assert sessions[0] == sm1.session_dir
        assert sessions[-1] == sm2.session_dir

    def test_filters_by_name(self, base: Path) -> None:
        sm_a = SessionManager(base, name="alpha")
        SessionManager(base, name="beta")
        reader = SessionManager(base, name="alpha", create=False)
        assert reader.list_sessions() == [sm_a.session_dir]

    def test_base_dir_override(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        sm = SessionManager(dir_a, name="run")
        reader = SessionManager(dir_b, name="run", create=False)
        assert reader.list_sessions(base_dir=dir_a) == [sm.session_dir]


# ── Archiving ─────────────────────────────────────────────────────────────────

class TestArchiving:
    def test_no_archive_below_threshold(self, base: Path) -> None:
        SessionManager(base, name="run", max_sessions=3)
        time.sleep(1.1)
        SessionManager(base, name="run", max_sessions=3)
        reader = SessionManager(base, name="run", create=False)
        assert len(reader.list_sessions()) == 2

    def test_oldest_moved_when_limit_reached(self, base: Path) -> None:
        sm1 = SessionManager(base, name="run", max_sessions=2)
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run", max_sessions=2)
        time.sleep(1.1)
        SessionManager(base, name="run", max_sessions=2)
        reader = SessionManager(base, name="run", create=False)
        active = reader.list_sessions()
        assert sm1.session_dir not in active
        assert sm2.session_dir in active

    def test_archived_to_default_subdir(self, base: Path) -> None:
        sm1 = SessionManager(base, name="run", max_sessions=1)
        time.sleep(1.1)
        SessionManager(base, name="run", max_sessions=1)
        assert (base / "archive" / sm1.session_dir.name).exists()

    def test_custom_archive_dir(self, tmp_path: Path) -> None:
        base = tmp_path / "results"
        custom_archive = tmp_path / "old_runs"
        sm1 = SessionManager(base, name="run", max_sessions=1, archive_dir=custom_archive)
        time.sleep(1.1)
        SessionManager(base, name="run", max_sessions=1, archive_dir=custom_archive)
        assert (custom_archive / sm1.session_dir.name).exists()

    def test_active_count_never_exceeds_max(self, base: Path) -> None:
        for _ in range(5):
            SessionManager(base, name="run", max_sessions=3)
            time.sleep(1.1)
        reader = SessionManager(base, name="run", create=False)
        assert len(reader.list_sessions()) <= 3


# ── Symlink ────────────────────────────────────────────────────────────────────

class TestSymlinkLatest:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="symlinks may require elevated privileges on Windows",
    )
    def test_symlink_points_to_session(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        link = sm.symlink_latest()
        assert link.resolve() == sm.session_dir.resolve()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="symlinks may require elevated privileges on Windows",
    )
    def test_symlink_updated_on_new_session(self, base: Path) -> None:
        sm1 = SessionManager(base, name="run")
        sm1.symlink_latest()
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        sm2.symlink_latest()
        link = base / "latest"
        assert link.resolve() == sm2.session_dir.resolve()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="symlinks may require elevated privileges on Windows",
    )
    def test_custom_symlink_name(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        link = sm.symlink_latest(name="current")
        assert (base / "current").resolve() == sm.session_dir.resolve()


# ── save_params ────────────────────────────────────────────────────────────────

class TestSaveParams:
    def test_creates_json_file(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        path = sm.save_params({"lr": 0.01, "epochs": 50})
        assert path.exists()
        assert path.suffix == ".json"

    def test_content_roundtrip(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        data = {"lr": 0.01, "epochs": 50, "model": "resnet"}
        path = sm.save_params(data)
        assert json.loads(path.read_text()) == data

    def test_custom_filename(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        path = sm.save_params({"x": 1}, filename="config.json")
        assert path.name == "config.json"

    def test_non_serialisable_falls_back_to_str(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        path = sm.save_params({"ts": datetime.now()})
        assert path.exists()


# ── save_env ───────────────────────────────────────────────────────────────────

class TestSaveEnv:
    def test_creates_file(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        path = sm.save_env()
        assert path.exists()

    def test_default_filename(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        path = sm.save_env()
        assert path.name == "environment.txt"

    def test_custom_filename(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        path = sm.save_env(filename="reqs.txt")
        assert path.name == "reqs.txt"

    def test_content_looks_like_pip_freeze(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        path = sm.save_env()
        content = path.read_text()
        assert "==" in content or content.strip() == ""


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
