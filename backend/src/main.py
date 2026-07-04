"""Compatibility entrypoint.

Use ``src.main_refactored:app`` for new local runs. This module remains so older
commands that reference ``src.main:app`` still start the same application.
"""

from .main_refactored import app, create_app

__all__ = ["app", "create_app"]
