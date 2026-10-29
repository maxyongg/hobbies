"""Source registry. To add a source: write a module with a Source subclass, list it here."""

from .afa import AsianFilmArchive
from .base import Source, SourceError
from .filmhouse import Filmhouse
from .shaw import Shaw

SOURCES: list[Source] = [Filmhouse(), Shaw(), AsianFilmArchive()]

__all__ = ["SOURCES", "Source", "SourceError"]
