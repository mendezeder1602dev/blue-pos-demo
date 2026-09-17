import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.authorization import authorization_context
from model.entity.models import Base
from model.repository.user import UserRepository


class UserSecurityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.repository = UserRepository(self.session)
        self.user = self.repository.create(
            'admin_seguridad', 'Clave-Segura-2026', '839201',
            role='superuser')

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_five_failed_logins_create_persistent_lock(self):
        for _ in range(UserRepository.MAX_ATTEMPTS):
            self.assertIsNone(
                self.repository.authenticate('admin_seguridad', 'incorrecta'))
        self.assertGreater(
            self.repository.login_block_seconds('admin_seguridad'), 0)
        self.assertIsNone(
            self.repository.authenticate('admin_seguridad', 'Clave-Segura-2026'))

    def test_password_reset_revokes_existing_sessions(self):
        token = self.repository.create_session(self.user)
        self.assertIsNotNone(self.repository.authenticate_session(token))
        self.repository.reset_password(
            'admin_seguridad', '839201', 'Nueva-Clave-Segura-2026')
        self.assertIsNone(self.repository.authenticate_session(token))

    def test_recovery_is_locked_after_repeated_failures(self):
        for _ in range(UserRepository.MAX_ATTEMPTS):
            with self.assertRaises(ValueError):
                self.repository.reset_password(
                    'admin_seguridad', 'incorrecto', 'Nueva-Clave-Segura-2026')
        self.assertIsNotNone(self.user.recovery_blocked_until)

    def test_rejects_common_or_single_class_passwords(self):
        with self.assertRaisesRegex(ValueError, 'demasiado común'):
            self.repository.create_seller(
                'Vendedor seguro', 'vendedor_seguro', 'admin1234', 'admin1234')
        with self.assertRaisesRegex(ValueError, 'combinar letras'):
            self.repository.create_seller(
                'Vendedor simple', 'vendedor_simple', 'sololetras', 'sololetras')

    def test_password_change_accepts_stronger_password_and_revokes_session(self):
        token = self.repository.create_session(self.user)
        self.repository.change_password(
            self.user.id, 'Clave-Segura-2026', 'Otra-Clave-2026', 'Otra-Clave-2026')
        self.assertIsNone(self.repository.authenticate_session(token))
        self.assertIsNotNone(
            self.repository.authenticate('admin_seguridad', 'Otra-Clave-2026'))

    def test_seller_cannot_manage_other_seller_accounts(self):
        seller = self.repository.create_seller(
            'Vendedor protegido', 'vendedor_protegido',
            'Clave-Vendedor-2026', 'Clave-Vendedor-2026')

        with authorization_context('seller'):
            with self.assertRaises(PermissionError):
                self.repository.set_seller_active(seller.id, False)
            with self.assertRaises(PermissionError):
                self.repository.reset_seller_password(
                    seller.id, 'Otra-Clave-2026', 'Otra-Clave-2026')


if __name__ == '__main__':
    unittest.main()
