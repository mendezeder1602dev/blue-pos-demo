import unittest

from model.authorization import authorization_context, require_role


class AuthorizationTest(unittest.TestCase):
    def test_seller_cannot_run_administrator_operation(self):
        with authorization_context('seller'):
            with self.assertRaises(PermissionError):
                require_role('superuser')

    def test_administrator_is_accepted(self):
        with authorization_context('superuser'):
            require_role('superuser')


if __name__ == '__main__':
    unittest.main()
