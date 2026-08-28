import hashlib
import os
import secrets
from datetime import datetime, timedelta
from sqlalchemy import delete, select
from model.entity.models import AuthSession, User


class UserRepository:
    MAX_ATTEMPTS = 5
    LOGIN_LOCK_MINUTES = 15
    RECOVERY_LOCK_MINUTES = 30
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
        if user is None:
            hashlib.pbkdf2_hmac('sha256', password.encode(), b'unknown-user', 260000)
            return None
        now = datetime.utcnow()
        if user.login_blocked_until and user.login_blocked_until > now:
            return None
        if not self._verify(password, user.password_hash):
            user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= self.MAX_ATTEMPTS:
                user.login_blocked_until = now + timedelta(minutes=self.LOGIN_LOCK_MINUTES)
                user.failed_login_attempts = 0
            self.__session.commit()
            return None
        user.failed_login_attempts = 0
        user.login_blocked_until = None
        self.__session.commit()
        return user

    def login_block_seconds(self, username):
        user = self.__session.scalars(select(User).where(User.username == username)).first()
        if not user or not user.login_blocked_until:
            return 0
        return max(0, int((user.login_blocked_until - datetime.utcnow()).total_seconds()))
    def create_session(self, user, duration_hours=12):
        token = secrets.token_urlsafe(32)
        session = AuthSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(hours=duration_hours),
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
        now = datetime.utcnow()
        if user and user.recovery_blocked_until and user.recovery_blocked_until > now:
            remaining = int((user.recovery_blocked_until - now).total_seconds())
            raise ValueError(f'Recuperación bloqueada temporalmente. Intenta de nuevo en {max(1, remaining // 60 + 1)} minutos.')
        if not user:
            hashlib.pbkdf2_hmac('sha256', recovery_code.encode(), b'unknown-user', 260000)
            raise ValueError('Datos de recuperación incorrectos.')
        if not self._verify(recovery_code, user.recovery_hash):
            user.failed_recovery_attempts = int(user.failed_recovery_attempts or 0) + 1
            if user.failed_recovery_attempts >= self.MAX_ATTEMPTS:
                user.recovery_blocked_until = now + timedelta(minutes=self.RECOVERY_LOCK_MINUTES)
                user.failed_recovery_attempts = 0
            self.__session.commit()
            raise ValueError('Datos de recuperación incorrectos.')
        if len(password) < 8: raise ValueError('La contraseña debe tener al menos 8 caracteres.')
        user.password_hash = self._hash(password)
        user.credential_version = int(user.credential_version or 0) + 1
        user.failed_login_attempts = 0
        user.failed_recovery_attempts = 0
        user.login_blocked_until = None
        user.recovery_blocked_until = None
        self.__session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        self.__session.commit()
