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

import logging
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class SessionConfig:
    """Injectable configuration for SessionManager.

    Attributes:
        timestamp_format: strftime format used to generate the timestamp
            component of the session folder name.
        separator: string placed between *name* and the timestamp.
    """

    timestamp_format: str = "%Y-%m-%d_%H-%M-%S"
    separator: str = "_"


_DEFAULTS = SessionConfig()


def _resolve_config(
    config: Optional[SessionConfig],
    separator: Optional[str],
) -> SessionConfig:
    """Return a SessionConfig applying the most-specific overrides first.

    Priority: explicit *separator* kwarg > *config* object > defaults.
    Uses :func:`dataclasses.replace` to avoid mutating the caller's object.
    """
    base = config if config is not None else _DEFAULTS
    return replace(base, separator=separator) if separator is not None else base


class SessionManager:
    """Creates or locates a timestamped session directory.

    Args:
        base_dir: Parent directory under which the session folder lives.
            Accepts both :class:`str` and :class:`~pathlib.Path`.
        name: Human-readable prefix for the session folder.
            Final folder name: ``<name><sep><timestamp>``.
            Pass an empty string to use the timestamp alone.
        separator: Quick override for the separator character(s) between
            *name* and the timestamp.  Takes precedence over *config*.
        config: Optional :class:`SessionConfig` for full control.
        create: If ``True`` (default) the session directory is created on
            disk immediately.  Pass ``False`` to build a configured object
            for use with :meth:`latest` without creating any folder.
        logger: Optional :class:`logging.Logger`.  When provided, the
            library emits its own internal events (folder created, scan
            results, errors) through this logger.  Pass your application
            logger so all output flows through the same handlers, formatters,
            and custom levels.  ``None`` (default) means silent.

    Example — script A, starting a new run::

        sm = SessionManager("results", name="preprocess", logger=logger)
        df.to_csv(sm.file("clean.csv"))

    Example — script B, picking up script A's latest output::

        sm = SessionManager("results", name="preprocess",
                            logger=logger, create=False)
        latest = sm.latest()
        logger.info("Using session: %s", latest)
        df = pd.read_csv(latest / "clean.csv")
    """

    def __init__(
        self,
        base_dir: str | Path,
        name: str = "session",
        *,
        separator: Optional[str] = None,
        config: Optional[SessionConfig] = None,
        create: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._config = _resolve_config(config, separator)
        self._name = name
        self._base_dir = Path(base_dir).resolve()
        self._log = logger

        if create:
            timestamp = datetime.now().strftime(self._config.timestamp_format)
            sep = self._config.separator
            folder = f"{name}{sep}{timestamp}" if name else timestamp
            self._session_dir: Optional[Path] = self._base_dir / folder
            self._session_dir.mkdir(parents=True, exist_ok=True)
            if self._log:
                self._log.debug("Session created: %s", self._session_dir)
        else:
            self._session_dir = None
            if self._log:
                self._log.debug(
                    "SessionManager initialised (create=False) — "
                    "base_dir=%s  name=%r", self._base_dir, self._name
                )

    # ── Alternative constructors ───────────────────────────────────────────────

    @classmethod
    def in_temp(
        cls,
        name: str = "session",
        *,
        separator: Optional[str] = None,
        config: Optional[SessionConfig] = None,
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
            config=config,
            logger=logger,
        )

    # ── Session discovery ──────────────────────────────────────────────────────

    def latest(self, base_dir: Optional[str | Path] = None) -> Path:
        """Return the path of the most recently created matching session folder.

        Scans *base_dir* (defaults to the base directory used at construction)
        for subdirectories whose names match ``<name><sep><timestamp>``,
        and returns the lexicographically largest one.

        Args:
            base_dir: Override the directory to scan.  Useful when script B
                needs to look in a different location from where it would
                write its own sessions.

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
                scan_dir, self._name, self._config.separator,
            )

        if not scan_dir.exists():
            if self._log:
                self._log.error("sessions_dir does not exist: %s", scan_dir)
            raise FileNotFoundError(f"sessions_dir does not exist: {scan_dir}")

        candidates = [p for p in scan_dir.iterdir() if p.is_dir()]

        if self._name:
            pattern = re.compile(
                r"^" + re.escape(f"{self._name}{self._config.separator}") + r"\d"
            )
            candidates = [p for p in candidates if pattern.match(p.name)]

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

        result = max(candidates, key=lambda p: p.name)
        if self._log:
            self._log.debug("Latest session: %s", result)
        return result

    # ── Public interface ───────────────────────────────────────────────────────

    @property
    def session_dir(self) -> Path:
        """Absolute path to this session's root directory.

        Raises:
            RuntimeError: If the instance was created with ``create=False``
                and no session directory exists yet.
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
