import pytest

from app import database


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run tests that call a real model provider (costs money)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live-model tests unless they were explicitly asked for.

    The deterministic suite must stay runnable by anyone, on any machine, with
    no credentials and no spend. Live tests are opted into with `--live` or
    `-m live`, never picked up by accident.
    """
    if config.getoption("--live") or "live" in (config.getoption("-m") or ""):
        return

    skip_live = pytest.mark.skip(
        reason="live model test -- run with `pytest -m live` (needs credentials)"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point every tool at a throwaway database for the duration of a test."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db(db)
    yield db
