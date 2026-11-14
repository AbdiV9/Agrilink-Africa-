# Owner: Person 1 (Backend & Database Lead)
"""Shared pytest fixtures: every test gets its own throwaway SQLite file.

The real ``agrilink.db`` is never touched, because ``AGRILINK_DB_PATH``
points ``Databases.db.get_connection`` at a temporary file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest

# Make "import Databases" / "import Auth" work when pytest runs from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Databases import Database_Setup  # noqa: E402


@pytest.fixture
def empty_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A temporary database with the schema created but no rows."""
    db_file = tmp_path / "test_agrilink.db"
    monkeypatch.setenv("AGRILINK_DB_PATH", str(db_file))
    Database_Setup.create_tables()
    yield db_file


@pytest.fixture
def seeded_db(empty_db: Path) -> Iterator[Path]:
    """A temporary database filled with the standard demo seed data."""
    Database_Setup.seed_data()
    yield empty_db
