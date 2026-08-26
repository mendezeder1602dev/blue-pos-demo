"""Reloj oficial de la operación de Puntos ECCOS.

La aplicación puede ejecutarse en servidores configurados en UTC. Estas funciones
evitan que ventas, cortes y movimientos cambien de fecha por la zona del servidor.
Se devuelve una fecha/hora local sin ``tzinfo`` porque las columnas SQL existentes
son ``DATETIME`` sin zona horaria.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


MEXICO_CENTRAL_TIMEZONE = ZoneInfo('America/Mexico_City')


def mexico_now() -> datetime:
    """Fecha y hora actual del centro de México, compatible con la base existente."""
    return datetime.now(MEXICO_CENTRAL_TIMEZONE).replace(tzinfo=None)


def mexico_today():
    """Fecha comercial actual según el horario del centro de México."""
    return mexico_now().date()
