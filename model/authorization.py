"""Autorización por ejecución para la capa de negocio."""

from contextlib import contextmanager
from contextvars import ContextVar


_role = ContextVar('puntos_eccos_role', default='system')


@contextmanager
def authorization_context(role):
    token = _role.set(role or '')
    try:
        yield
    finally:
        _role.reset(token)


def require_role(*allowed_roles):
    current = _role.get()
    if current != 'system' and current not in allowed_roles:
        raise PermissionError('La cuenta actual no tiene permiso para realizar esta operación.')
