"""
session_manager.session
~~~~~~~~~~~~~~~~~~~~~~~
Lightweight session-directory manager for data-processing scripts.

Each SessionManager instance represents one run: it creates a uniquely
timestamped folder under a caller-supplied base directory and exposes
helper methods for building paths inside that folder.

The class intentionally does *not* handle saving data — that stays with
the caller.  Its single responsibility is directory lifecycle.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
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


class SessionManager:
    """Creates and owns a timestamped session directory.

    Args:
        base_dir: Parent directory under which the session folder is created.
            Accepts both :class:`str` and :class:`~pathlib.Path`.
            Created automatically if it does not exist.
        name: Human-readable prefix for the session folder.
            The final folder name is ``<name><sep><timestamp>``.
            Pass an empty string to use the timestamp alone.
        config: Optional :class:`SessionConfig` instance.  Defaults are used
            when *config* is ``None``.

    Raises:
        OSError: If the session directory cannot be created.

    Example::

        sm = SessionManager("results", name="rna_seq")
        df.to_csv(sm.file("counts.csv"))
        fig.savefig(sm.file("volcano.png"))
        plots = sm.subdir("plots")
        fig2.savefig(plots / "pca.png")
    """

    def __init__(
        self,
        base_dir: str | Path,
        name: str = "session",
        config: Optional[SessionConfig] = None,
    ) -> None:
        self._config = config or SessionConfig()
        timestamp = datetime.now().strftime(self._config.timestamp_format)
        sep = self._config.separator
        folder = f"{name}{sep}{timestamp}" if name else timestamp
        self._session_dir = Path(base_dir).resolve() / folder
        self._session_dir.mkdir(parents=True, exist_ok=True)

    # ── Alternative constructors ───────────────────────────────────────────────

    @classmethod
    def in_temp(
        cls,
        name: str = "session",
        config: Optional[SessionConfig] = None,
    ) -> "SessionManager":
        """Create a session inside the system temporary directory.

        Useful for intermediate results that do not need to persist across
        reboots or when you do not want to specify an explicit output path.

        Args:
            name: Session name prefix (see :class:`SessionManager`).
            config: Optional :class:`SessionConfig` instance.

        Returns:
            A new :class:`SessionManager` (or subclass) rooted in
            ``tempfile.gettempdir()``.

        Example::

            sm = SessionManager.in_temp(name="scratch")
            # session lives under /tmp/ (Linux/macOS) or %TEMP% (Windows)
        """
        return cls(Path(tempfile.gettempdir()), name=name, config=config)

    # ── Static helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def latest(
        sessions_dir: str | Path,
        name: Optional[str] = None,
        config: Optional[SessionConfig] = None,
    ) -> Path:
        """Return the path of the most recently created session folder.

        Scans *sessions_dir* for subdirectories, optionally filtering by name
        prefix, and returns the one with the lexicographically largest name
        (which equals the latest timestamp when the default
        ``%Y-%m-%d_%H-%M-%S`` format is used).

        Args:
            sessions_dir: Directory that contains session folders
                (i.e. the *base_dir* passed when creating sessions).
            name: Optional prefix filter.
            config: Optional :class:`SessionConfig`.  When provided together
                with *name*, the filter uses the exact
                ``<name><separator>`` prefix (e.g. ``"run--"`` for
                ``separator="--"``), avoiding false matches against folders
                whose names merely *start with* the same string
                (e.g. ``"run_extra_..."``) .  When *config* is ``None`` the
                filter falls back to a plain ``startswith(name)`` check,
                which works across all separators but is less precise.

        Returns:
            :class:`~pathlib.Path` pointing to the latest session folder.

        Raises:
            FileNotFoundError: If *sessions_dir* does not exist.
            ValueError: If no matching session folder is found.

        Example::

            cfg = SessionConfig(separator="--")

            # Script A — writes with custom separator
            sm = SessionManager("results", name="preprocess", config=cfg)

            # Script B — exact match, no ambiguity
            latest = SessionManager.latest("results", name="preprocess", config=cfg)
            df = pd.read_csv(latest / "output.csv")
        """
        base = Path(sessions_dir).resolve()
        if not base.exists():
            raise FileNotFoundError(f"sessions_dir does not exist: {base}")

        candidates = [p for p in base.iterdir() if p.is_dir()]

        if name is not None:
            sep = config.separator if config is not None else None
            if sep is not None:
                # Require name+sep followed immediately by a digit (start of
                # timestamp), so "run_" does not accidentally match "run_extra_".
                import re as _re
                pattern = _re.compile(r"^" + _re.escape(f"{name}{sep}") + r"\d")
                candidates = [p for p in candidates if pattern.match(p.name)]
            else:
                candidates = [p for p in candidates if p.name.startswith(name)]

        if not candidates:
            qualifier = f" matching name={name!r}" if name else ""
            raise ValueError(
                f"No session folders found in {base}{qualifier}"
            )

        return max(candidates, key=lambda p: p.name)

    # ── Public interface ───────────────────────────────────────────────────────

    @property
    def session_dir(self) -> Path:
        """Absolute path to this session's root directory."""
        return self._session_dir

    def file(self, *parts: str) -> Path:
        """Return an absolute path for a file inside the session directory.

        Intermediate directories are *not* created automatically; use
        :meth:`subdir` when you need a subdirectory to exist first.

        Args:
            *parts: Path components joined relative to *session_dir*.

        Returns:
            A :class:`~pathlib.Path` pointing inside the session directory.
        """
        return self._session_dir.joinpath(*parts)

    def subdir(self, *parts: str) -> Path:
        """Create a subdirectory inside the session directory and return it.

        Args:
            *parts: Path components for the subdirectory, joined relative to
                *session_dir*.

        Returns:
            The created :class:`~pathlib.Path`.
        """
        path = self._session_dir.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ── Dunder helpers ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"{type(self).__name__}(session_dir={str(self._session_dir)!r})"

    def __truediv__(self, other: str) -> Path:
        """Support the ``sm / 'filename'`` shorthand."""
        return self._session_dir / other
