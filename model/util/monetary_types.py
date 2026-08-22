from money import Money

MONEY_CURRENCY = 'MXN'


def MXNMoney(amount: str) -> Money:
    """Crea importes en pesos mexicanos (MXN)."""
    return Money(amount=amount, currency=MONEY_CURRENCY)


# Compatibilidad temporal para extensiones y bases de pruebas de Blue POS.
# El nombre histórico se conserva, pero ya siempre crea importes MXN.
def CUPMoney(amount: str) -> Money:
    return MXNMoney(amount)
