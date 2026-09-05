import pytest

from app import database


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point every tool at a throwaway database for the duration of a test."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db(db)
    yield db
