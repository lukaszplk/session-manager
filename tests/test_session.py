"""Tests for SessionManager and SessionConfig."""

import re
from pathlib import Path

import pytest

from session_manager import SessionConfig, SessionManager


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def base(tmp_path: Path) -> Path:
    return tmp_path / "results"


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
        pattern = r"^analysis_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        assert re.match(pattern, sm.session_dir.name)

    def test_no_name_uses_timestamp_only(self, base: Path) -> None:
        sm = SessionManager(base, name="")
        pattern = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        assert re.match(pattern, sm.session_dir.name)

    def test_creates_base_dir_if_missing(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        assert not deep.exists()
        SessionManager(deep, name="run")
        assert deep.exists()

    def test_two_instances_get_different_dirs(self, base: Path) -> None:
        import time
        sm1 = SessionManager(base, name="run")
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        assert sm1.session_dir != sm2.session_dir


# ── SessionConfig injection ────────────────────────────────────────────────────

class TestSessionConfig:
    def test_custom_timestamp_format(self, base: Path) -> None:
        cfg = SessionConfig(timestamp_format="%Y%m%d")
        sm = SessionManager(base, name="run", config=cfg)
        pattern = r"^run_\d{8}$"
        assert re.match(pattern, sm.session_dir.name)

    def test_custom_separator(self, base: Path) -> None:
        cfg = SessionConfig(separator="--")
        sm = SessionManager(base, name="run", config=cfg)
        assert sm.session_dir.name.startswith("run--")

    def test_default_config_used_when_none(self, base: Path) -> None:
        sm = SessionManager(base, name="run", config=None)
        pattern = r"^run_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        assert re.match(pattern, sm.session_dir.name)


# ── Path helpers ───────────────────────────────────────────────────────────────

class TestPathHelpers:
    def test_file_returns_path_inside_session(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        p = sm.file("output.csv")
        assert p.parent == sm.session_dir
        assert p.name == "output.csv"

    def test_file_accepts_multiple_parts(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        p = sm.file("plots", "volcano.png")
        assert p == sm.session_dir / "plots" / "volcano.png"

    def test_subdir_creates_directory(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        d = sm.subdir("plots")
        assert d.exists()
        assert d.is_dir()

    def test_subdir_returns_correct_path(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        d = sm.subdir("nested", "deep")
        assert d == sm.session_dir / "nested" / "deep"
        assert d.exists()

    def test_truediv_shorthand(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm / "file.txt" == sm.session_dir / "file.txt"


# ── Repr ───────────────────────────────────────────────────────────────────────

class TestRepr:
    def test_repr_contains_class_name(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert "SessionManager" in repr(sm)

    def test_repr_contains_path(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.name in repr(sm)
