"""
session_manager.session
~~~~~~~~~~~~~~~~~~~~~~~
Lightweight session-directory manager for data-processing scripts.

Each SessionManager instance represents one run: it creates (or locates)
a uniquely timestamped folder under a caller-supplied base directory and
exposes helper methods for building paths inside that folder.

The class intentionally does *not* handle saving data — that stays with
the caller.  Its single responsibility is directory lifecycle.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_DEFAULT_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
_DEFAULT_SEPARATOR = "_"
_DEFAULT_ARCHIVE_DIR = "archive"


class SessionManager:
    """Creates or locates a timestamped session directory.

    Args:
        base_dir: Parent directory under which the session folder lives.
            Accepts both :class:`str` and :class:`~pathlib.Path`.
            Created automatically if it does not exist.
            Defaults to ``sm-sessions/`` inside the current working directory.
        name: Human-readable prefix for the session folder.
            Final folder name: ``<name><separator><timestamp>``.
            Pass an empty string to use the timestamp alone.
        separator: String placed between *name* and the timestamp.
            Defaults to ``"_"``.
        timestamp_format: :func:`~datetime.datetime.strftime` format for the
            timestamp component.  Defaults to ``"%Y-%m-%d_%H-%M-%S"``.
        create: If ``True`` (default) the session directory is created on
            disk immediately.  Pass ``False`` to build a configured object
            for use with :meth:`latest` or :meth:`list_sessions` without
            creating any folder.
        max_sessions: Maximum number of matching session folders to keep in
            *base_dir*.  When a new session is created and the existing count
            reaches this limit, the oldest folder(s) are moved to
            *archive_dir* before the new session is created.  ``None``
            (default) disables archiving.
        archive_dir: Destination for archived sessions.  Accepts both
            :class:`str` and :class:`~pathlib.Path`.  Defaults to an
            ``archive/`` subdirectory inside *base_dir*.  Ignored when
            *max_sessions* is ``None``.
        logger: Optional :class:`logging.Logger`.  When provided, the
            library routes its internal events (folder created, scan
            results, errors) through this logger so all output flows
            through your handlers, formatters, and custom levels.
            ``None`` (default) is fully silent.

    Example — script A, starting a new run::

        sm = SessionManager("results", name="preprocess", logger=logger)
        df.to_csv(sm.file("clean.csv"))

    Example — script B, picking up script A's latest output::

        sm = SessionManager("results", name="preprocess",
                            logger=logger, create=False)
        latest = sm.latest()
        logger.info("Using session: %s", latest)
        df = pd.read_csv(latest / "clean.csv")

    Example — keep only the 5 most recent sessions, archive the rest::

        sm = SessionManager("results", name="run", max_sessions=5)
    """

    def __init__(
        self,
        base_dir: Optional[str | Path] = None,
        name: str = "session",
        *,
        separator: str = _DEFAULT_SEPARATOR,
        timestamp_format: str = _DEFAULT_TIMESTAMP_FORMAT,
        create: bool = True,
        max_sessions: Optional[int] = None,
        archive_dir: Optional[str | Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._name = name
        self._separator = separator
        self._timestamp_format = timestamp_format
        self._base_dir = (
            Path(base_dir).resolve()
            if base_dir is not None
            else Path.cwd() / "sm-sessions"
        )
        self._max_sessions = max_sessions
        self._archive_dir: Optional[Path] = (
            Path(archive_dir).resolve()
            if archive_dir is not None
            else self._base_dir / _DEFAULT_ARCHIVE_DIR
        )
        self._log = logger
        self._session_dir: Optional[Path] = None

        if create:
            if max_sessions is not None:
                self._archive_overflow(max_sessions)
            timestamp = datetime.now().strftime(self._timestamp_format)
            folder = f"{name}{separator}{timestamp}" if name else timestamp
            self._session_dir = self._base_dir / folder
            self._session_dir.mkdir(parents=True, exist_ok=True)
            if self._log:
                self._log.debug("Session created: %s", self._session_dir)
        else:
            if self._log:
                self._log.debug(
                    "SessionManager initialised (create=False) — "
                    "base_dir=%s  name=%r", self._base_dir, self._name,
                )

    # ── Alternative constructors ───────────────────────────────────────────────

    @classmethod
    def in_temp(
        cls,
        name: str = "session",
        *,
        separator: str = _DEFAULT_SEPARATOR,
        timestamp_format: str = _DEFAULT_TIMESTAMP_FORMAT,
        logger: Optional[logging.Logger] = None,
    ) -> "SessionManager":
        """Create a session inside the system temporary directory.

        Convenience constructor — identical to passing
        ``Path(tempfile.gettempdir())`` as *base_dir*, without needing to
        import :mod:`tempfile` or know the OS-specific temp path.

        Returns the same type as the receiver, so subclasses work correctly.
        """
        return cls(
            Path(tempfile.gettempdir()),
            name=name,
            separator=separator,
            timestamp_format=timestamp_format,
            logger=logger,
        )

    # ── Session discovery ──────────────────────────────────────────────────────

    def _matching_sessions(self, scan_dir: Path) -> list[Path]:
        """Return session folders in *scan_dir* matching this instance's name/separator, oldest first."""
        if not scan_dir.exists():
            return []
        candidates = [p for p in scan_dir.iterdir() if p.is_dir()]
        if self._name:
            pattern = re.compile(
                r"^" + re.escape(f"{self._name}{self._separator}") + r"\d"
            )
            candidates = [p for p in candidates if pattern.match(p.name)]
        return sorted(candidates, key=lambda p: p.name)

    def list_sessions(self, base_dir: Optional[str | Path] = None) -> list[Path]:
        """Return all matching session folders, sorted oldest-first.

        Args:
            base_dir: Directory to scan.  Defaults to the base directory used
                at construction.

        Returns:
            List of :class:`~pathlib.Path` objects, oldest first.  Empty list
            if the directory does not exist or contains no matches.
        """
        scan_dir = Path(base_dir).resolve() if base_dir is not None else self._base_dir
        sessions = self._matching_sessions(scan_dir)
        if self._log:
            self._log.debug(
                "list_sessions: found %d session(s) in %s", len(sessions), scan_dir
            )
        return sessions

    def latest(self, base_dir: Optional[str | Path] = None) -> Path:
        """Return the path of the most recently created matching session folder.

        Scans *base_dir* (defaults to the base directory used at construction)
        for subdirectories whose names match ``<name><separator><timestamp>``,
        and returns the lexicographically largest one.

        Args:
            base_dir: Override the directory to scan.  Useful when script B
                needs to look in a different location from its own base_dir.

        Returns:
            :class:`~pathlib.Path` to the latest matching session folder.

        Raises:
            FileNotFoundError: If the target directory does not exist.
            ValueError: If no matching session folder is found.
        """
        scan_dir = Path(base_dir).resolve() if base_dir is not None else self._base_dir

        if self._log:
            self._log.debug(
                "Scanning %s for sessions matching name=%r separator=%r",
                scan_dir, self._name, self._separator,
            )

        if not scan_dir.exists():
            if self._log:
                self._log.error("sessions_dir does not exist: %s", scan_dir)
            raise FileNotFoundError(f"sessions_dir does not exist: {scan_dir}")

        candidates = self._matching_sessions(scan_dir)

        if self._log:
            self._log.debug("Found %d candidate session(s)", len(candidates))

        if not candidates:
            msg = (
                f"No session folders found in {scan_dir} "
                f"matching name={self._name!r}"
            )
            if self._log:
                self._log.warning(msg)
            raise ValueError(msg)

        result = candidates[-1]
        if self._log:
            self._log.debug("Latest session: %s", result)
        return result

    # ── Archiving ─────────────────────────────────────────────────────────────

    def _archive_overflow(self, max_sessions: int) -> None:
        """Move oldest sessions to the archive dir if count >= *max_sessions*."""
        existing = self._matching_sessions(self._base_dir)
        overflow = len(existing) - max_sessions + 1  # +1 to make room for the new one
        if overflow <= 0:
            return
        assert self._archive_dir is not None
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        for folder in existing[:overflow]:
            dest = self._archive_dir / folder.name
            shutil.move(str(folder), str(dest))
            if self._log:
                self._log.debug("Archived session: %s → %s", folder, dest)

    # ── Symlink ───────────────────────────────────────────────────────────────

    def symlink_latest(self, name: str = "latest") -> Path:
        """Create or update a symlink ``<base_dir>/<name>`` pointing to the
        current session directory.

        Useful so downstream scripts can always read from a stable path
        (e.g. ``results/latest/``) without calling :meth:`latest`.

        Args:
            name: Name of the symlink inside *base_dir*.  Defaults to
                ``"latest"``.

        Returns:
            Path to the symlink.

        Note:
            On Windows, creating symlinks requires Developer Mode or elevated
            privileges.  A :exc:`OSError` is raised if the operation is not
            permitted.
        """
        link = self._base_dir / name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(self.session_dir, target_is_directory=True)
        if self._log:
            self._log.debug("Symlink updated: %s → %s", link, self.session_dir)
        return link

    # ── Save helpers ──────────────────────────────────────────────────────────

    def save_params(
        self,
        data: dict[str, Any],
        filename: str = "params.json",
    ) -> Path:
        """Serialise *data* as pretty-printed JSON inside the session directory.

        Args:
            data: Any JSON-serialisable dict (strings, numbers, booleans,
                lists, nested dicts).
            filename: Output filename.  Defaults to ``"params.json"``.

        Returns:
            :class:`~pathlib.Path` to the written file.
        """
        path = self.file(filename)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        if self._log:
            self._log.debug("Params saved: %s", path)
        return path

    def save_env(self, filename: str = "environment.txt") -> Path:
        """Save the current ``pip freeze`` output inside the session directory.

        Captures the exact package versions installed in the running Python
        environment so the run can be reproduced later.

        Args:
            filename: Output filename.  Defaults to ``"environment.txt"``.

        Returns:
            :class:`~pathlib.Path` to the written file.

        Raises:
            RuntimeError: If ``pip freeze`` fails (e.g. pip not available).
        """
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pip freeze failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        path = self.file(filename)
        path.write_text(result.stdout, encoding="utf-8")
        if self._log:
            self._log.debug("Environment saved: %s", path)
        return path

    # ── Public interface ───────────────────────────────────────────────────────

    @property
    def session_dir(self) -> Path:
        """Absolute path to this session's root directory.

        Raises:
            RuntimeError: If the instance was created with ``create=False``.
        """
        if self._session_dir is None:
            raise RuntimeError(
                "session_dir is not available: this instance was created with "
                "create=False.  Call latest() to locate an existing session."
            )
        return self._session_dir

    def file(self, *parts: str) -> Path:
        """Return a path for a file inside the session directory (not created).

        Args:
            *parts: Path components joined relative to *session_dir*.
        """
        return self.session_dir.joinpath(*parts)

    def subdir(self, *parts: str) -> Path:
        """Create a subdirectory inside the session directory and return it.

        Args:
            *parts: Path components for the subdirectory.
        """
        path = self.session_dir.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ── Dunder helpers ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"session_dir={str(self._session_dir)!r}, "
            f"name={self._name!r})"
        )

    def __truediv__(self, other: str) -> Path:
        """Support the ``sm / 'filename'`` shorthand."""
        return self.session_dir / other
