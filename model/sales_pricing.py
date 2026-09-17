"""Reglas de precio del punto de venta."""


def sale_unit_price(product, quantity, configured_price=None, locked_price=None):
    """Devuelve el precio explícito sin descuentos automáticos por cantidad."""
    del quantity  # La cantidad no modifica el precio unitario de forma implícita.
    if locked_price is not None:
        return float(locked_price)
    if configured_price is not None:
        return float(configured_price)
    return float(product.price.amount)
