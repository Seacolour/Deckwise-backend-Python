"""Models actually callable through the current Python API."""

from app.schemas.model import AvailableModelDTO


def available_models() -> list[AvailableModelDTO]:
    # No conversation execution endpoint is registered yet. Publishing model IDs
    # now would enable the Web send button for requests that cannot be handled.
    return []
