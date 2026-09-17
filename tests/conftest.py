"""Shared pytest lifecycle for the repository's SQLite integration tests."""

import pytest

from model.repository.factory import RepositoryFactory
from tests.settings import set_up, tear_down


@pytest.fixture(scope='session', autouse=True)
def initialized_test_database():
    """Create the ignored test database in clean checkouts and remove it after."""
    set_up()
    try:
        yield
    finally:
        RepositoryFactory.close_session()
        tear_down()
