"""Persistence adapters for anonymous recommendation analytics."""

from heritagelink.repositories.choice_repository import ChoiceRepository
from heritagelink.repositories.memory_artisan_draft_repository import (
    MemoryArtisanDraftRepository,
)
from heritagelink.repositories.memory_choice_repository import MemoryChoiceRepository
from heritagelink.repositories.postgres_choice_repository import PostgresChoiceRepository
from heritagelink.repositories.sqlite_artisan_draft_repository import (
    SQLiteArtisanDraftRepository,
)
from heritagelink.repositories.sqlite_choice_repository import SQLiteChoiceRepository

__all__ = [
    "ChoiceRepository",
    "MemoryArtisanDraftRepository",
    "MemoryChoiceRepository",
    "PostgresChoiceRepository",
    "SQLiteChoiceRepository",
    "SQLiteArtisanDraftRepository",
]
