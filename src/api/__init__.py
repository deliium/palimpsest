"""HTTP composition root. Does not mutate domain state directly."""

from api.app import create_app

__all__ = ["create_app"]
