"""
BlueDolphin adapter: placeholder.

  Application Component            -> Application (source_system 'bluedolphin')
  Application Interface            -> Connection metadata (name, interface_id)
  Flow / Serving relationship      -> Connection
      "A serves B" means B depends on A: source = B, target = A
  Technology Service / Node        -> Application.it_components, Connection.via
  Data Object (via Access)         -> data_objects
  Object lifecycle / status        -> lifecycle_status / lifecycle_dates

The adapter should produce a RawBundle like load_leanix() so it plugs into
the shared assemble() step without other changes.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .records import RawBundle


class BlueDolphinNotSupportedError(NotImplementedError):
    """Raised until the BlueDolphin adapter is implemented."""


def load_bluedolphin(paths: Iterable[str | Path]) -> RawBundle:
    raise BlueDolphinNotSupportedError(
        "The BlueDolphin adapter is not implemented yet."
    )
