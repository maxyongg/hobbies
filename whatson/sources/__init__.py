"""Source registry. To add a source: write a module with a Source subclass, list it here.

Sources with alerts = False appear in the web app but never push.
"""

from .afa import AsianFilmArchive
from .base import Source, SourceError
from .carnival import Carnival
from .filmhouse import Filmhouse
from .gv import GoldenVillage
from .sfs import SingaporeFilmSociety
from .shaw import Shaw

SOURCES: list[Source] = [
    Filmhouse(), Shaw(), AsianFilmArchive(),  # alert on new films
    GoldenVillage(), Carnival(), SingaporeFilmSociety(),  # web app only
]

__all__ = ["SOURCES", "Source", "SourceError"]
