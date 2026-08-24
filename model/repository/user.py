import hashlib
import os
import secrets
from datetime import datetime, timedelta
from sqlalchemy import select
from model.entity.models import AuthSession, User


class UserRepository:
    def __init__(self, session): self.__session = session
    @staticmethod
    def _hash(value, salt=None):
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), 260000).hex()
        return f'{salt}${digest}'
    @staticmethod
    def _verify(value, stored):
        salt, digest = stored.split('$', 1)
        return secrets.compare_digest(UserRepository._hash(value, salt).split('$', 1)[1], digest)
    def has_users(self): return self.__session.scalars(select(User)).first() is not None
    def has_superuser(self):
        return self.__session.scalars(select(User).where(User.role == 'superuser')).first() is not None
    def bootstrap_administrator(self):
        """Crea el único jefe de tienda y migra el nombre corporativo previo."""
        administrator = self.__session.scalars(select(User).where(User.role == 'superuser')).first()
        if administrator is None:
            username = os.getenv('BLUE_POS_ADMIN_USER')
            password = os.getenv('BLUE_POS_ADMIN_PASSWORD')
            recovery_code = os.getenv('BLUE_POS_RECOVERY_CODE')
            if not username or not password or not recovery_code:
                raise RuntimeError(
                    'Configura BLUE_POS_ADMIN_USER, BLUE_POS_ADMIN_PASSWORD y '
                    'BLUE_POS_RECOVERY_CODE como secretos privados antes de iniciar el sistema.')
            administrator = self.create(username, password, recovery_code,
                                        'superuser', 'Administrador', 'primary')
            administrator.credential_version = 2
            self.__session.commit()
            return administrator
        if administrator.username == 'GrupoEccos':
            administrator.username = 'Administrador'
            administrator.display_name = 'Administrador'
            administrator.workspace_key = 'primary'
        # Se actualiza una única vez para migrar credenciales creadas con la
        # configuración anterior. Después, el cambio de contraseña persiste.
        return administrator
    def create(self, username, password, recovery_code, role='store', display_name='', workspace_key='primary'):
        if not username or len(password) < 8 or len(recovery_code) < 4: raise ValueError('Usuario, contraseña de 8 caracteres y código de recuperación son obligatorios.')
        if role == 'superuser' and self.has_superuser(): raise ValueError('Ya existe un superusuario. El sistema sólo permite uno.')
        if self.__session.scalars(select(User).where(User.username == username)).first(): raise ValueError('Ese usuario ya existe.')
        user = User(username=username.strip(), password_hash=self._hash(password), recovery_hash=self._hash(recovery_code), role=role, display_name=display_name or username, workspace_key=workspace_key)
        self.__session.add(user); self.__session.commit(); return user
    def authenticate(self, username, password):
        user = self.__session.scalars(select(User).where(User.username == username)).first()
        return user if user and self._verify(password, user.password_hash) else None
    def create_session(self, user, duration_days=7):
        token = secrets.token_urlsafe(32)
        session = AuthSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=duration_days),
        )
        self.__session.add(session)
        self.__session.commit()
        return token
    def authenticate_session(self, token):
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = self.__session.scalars(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        ).first()
        if session is None:
            return None
        if session.expires_at <= datetime.utcnow():
            self.__session.delete(session)
            self.__session.commit()
            return None
        return session.user
    def revoke_session(self, token):
        if not token:
            return
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = self.__session.scalars(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        ).first()
        if session is not None:
            self.__session.delete(session)
            self.__session.commit()
    def reset_password(self, username, recovery_code, password):
        user = self.__session.scalars(select(User).where(User.username == username)).first()
        if not user or not self._verify(recovery_code, user.recovery_hash): raise ValueError('Datos de recuperación incorrectos.')
        if len(password) < 8: raise ValueError('La contraseña debe tener al menos 8 caracteres.')
        user.password_hash = self._hash(password); self.__session.commit()
