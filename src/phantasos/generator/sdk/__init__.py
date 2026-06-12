"""SDK generation pipeline: preprocess -> generate (OAG) -> patch -> vendor -> smoke."""

from .build import build

__all__ = ["build"]
