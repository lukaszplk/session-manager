"""
session_manager.session
~~~~~~~~~~~~~~~~~~~~~~~
Lightweight session-directory manager for data-processing scripts.

Each SessionManager instance represents one run:  it creates a uniquely
timestamped folder under a caller-supplied base directory and exposes
helper methods for building paths inside that folder.

The class intentionally does *not* handle saving data — that stays with
the caller.  Its single responsibility is directory lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


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
    """

    def __init__(
        self,
        base_dir: str | Path,
        name: str = "session",
        config: SessionConfig | None = None,
    ) -> None:
        self._config = config or SessionConfig()
        timestamp = datetime.now().strftime(self._config.timestamp_format)
        sep = self._config.separator
        folder = f"{name}{sep}{timestamp}" if name else timestamp
        self._session_dir = Path(base_dir).resolve() / folder
        self._session_dir.mkdir(parents=True, exist_ok=True)

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
