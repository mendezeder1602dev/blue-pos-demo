import unittest

from model.repository.cash_control import CashControlRepository
from model.repository.factory import RepositoryFactory
from tests.util.general import TEST_DB_URL


class RepositoryFactoryReloadTest(unittest.TestCase):
    def tearDown(self):
        RepositoryFactory.close_session()

    def test_replaces_a_cached_repository_from_a_previous_hot_reload(self):
        RepositoryFactory.activate_workspace(TEST_DB_URL)
        legacy_repository = object()
        RepositoryFactory._RepositoryFactory__cash_control_repository = legacy_repository

        repository = RepositoryFactory.get_cash_control_repository()

        self.assertIsInstance(repository, CashControlRepository)
        self.assertIsNot(repository, legacy_repository)
        self.assertTrue(callable(repository.get_unclosed_opening))

    def test_replaces_cached_repository_missing_the_fleet_query(self):
        class PartiallyReloadedRepository:
            @staticmethod
            def get_unclosed_opening(_register_id):
                return None

        RepositoryFactory.activate_workspace(TEST_DB_URL)
        legacy_repository = PartiallyReloadedRepository()
        RepositoryFactory._RepositoryFactory__cash_control_repository = legacy_repository

        repository = RepositoryFactory.get_cash_control_repository()

        self.assertIsInstance(repository, CashControlRepository)
        self.assertTrue(callable(repository.get_unclosed_openings))


if __name__ == '__main__':
    unittest.main()
