"""Reglas compartidas para la configuración de métodos de pago."""
import json


PAYMENT_METHODS = ('Efectivo', 'Transferencia', 'Tarjeta', 'Crédito', 'Mixto', 'Vale')
CASH_PAYMENT_METHOD = 'Efectivo'


def normalize_enabled_payment_methods(configured):
    """Devuelve métodos válidos, manteniendo siempre el efectivo disponible."""
    if not configured:
        return PAYMENT_METHODS
    try:
        stored = json.loads(configured)
    except (TypeError, ValueError, json.JSONDecodeError):
        return PAYMENT_METHODS
    if not isinstance(stored, list):
        return PAYMENT_METHODS

    enabled = set(stored)
    return tuple(method for method in PAYMENT_METHODS
                 if method == CASH_PAYMENT_METHOD or method in enabled)
