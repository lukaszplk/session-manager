from importlib.metadata import version, PackageNotFoundError
from .session import SessionManager

try:
    __version__ = version("session-manager")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["SessionManager", "__version__"]
