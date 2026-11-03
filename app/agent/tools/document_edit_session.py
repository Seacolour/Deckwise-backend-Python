"""A document working copy scoped to one Agent turn."""

from dataclasses import dataclass


@dataclass
class DocumentEditSession:
    version: int
    content: str
    modified: bool = False
    full_read: bool = False
