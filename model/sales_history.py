"""Read-only helpers for presenting a sale as one complete operation.

The database stores one ``Sale`` row per sold unit.  These helpers group those
rows for history screens and documents without changing the saved transaction.
"""

from collections import OrderedDict
from datetime import datetime, time


def _product_name(sale) -> str:
    snapshot_name = (getattr(sale, 'product_name', '') or '').strip()
    if snapshot_name:
        return snapshot_name
    product = getattr(sale, 'product', None)
    product_name = (getattr(product, 'name', '') or '').strip()
    return product_name or f'Producto #{getattr(sale, "product_id", "—")}'


def _amount(sale) -> float:
    value = getattr(getattr(sale, 'price', None), 'amount', 0)
    return float(value or 0)


def build_sale_detail(sales) -> dict:
    """Group the unit rows of one transaction into a stable operation detail."""
    ordered_sales = sorted(list(sales), key=lambda sale: int(getattr(sale, 'id', 0) or 0))
    if not ordered_sales:
        raise ValueError('No se puede construir el detalle de una venta vacía.')

    first = ordered_sales[0]
    timestamps = [
        sale.created_at for sale in ordered_sales
        if isinstance(getattr(sale, 'created_at', None), datetime)
    ]
    if timestamps:
        created_at = min(timestamps)
    else:
        created_at = datetime.combine(first.date, time.min)

    grouped = OrderedDict()
    distinct_products = set()
    for sale in ordered_sales:
        name = _product_name(sale)
        unit_price = _amount(sale)
        product_id = getattr(sale, 'product_id', None)
        distinct_products.add(product_id if product_id is not None else name)
        # Keep different prices separate. This preserves discounted or corrected
        # line values instead of displaying a misleading averaged unit price.
        key = (product_id, name, unit_price)
        row = grouped.setdefault(key, {
            'Producto': name,
            'Cantidad': 0,
            'Precio unitario': unit_price,
            'Importe': 0.0,
        })
        row['Cantidad'] += 1
        row['Importe'] = round(row['Importe'] + unit_price, 2)

    items = tuple(grouped.values())
    return {
        'first_sale_id': min(int(sale.id) for sale in ordered_sales),
        'transaction_id': getattr(first, 'transaction_id', None),
        'created_at': created_at,
        'date_label': created_at.strftime('%d/%m/%Y'),
        'time_label': created_at.strftime('%H:%M:%S'),
        'payment_method': getattr(first, 'payment_method', '') or 'Sin método',
        'payment_details': getattr(first, 'payment_details', '') or '',
        'customer': getattr(first, 'customer', '') or 'Público general',
        'cashier': getattr(first, 'cashier', '') or 'Vendedor',
        'register_name': getattr(first, 'register_name', '') or 'Caja principal',
        'status': getattr(first, 'status', '') or 'Sin estado',
        'unit_count': len(ordered_sales),
        'distinct_product_count': len(distinct_products),
        'total': round(sum(item['Importe'] for item in items), 2),
        'items': items,
    }


def sale_detail_pdf_sections(detail: dict, folio: str) -> tuple:
    """Return A4 report sections for a sale, separate from the thermal ticket."""
    operation = [{
        'Folio': folio,
        'Fecha': detail['date_label'],
        'Hora': detail['time_label'],
        'Estado': detail['status'],
        'Método de pago': detail['payment_method'],
        'Cliente': detail['customer'],
        'Responsable': detail['cashier'],
        'Caja': detail['register_name'],
        'Detalle del pago': detail['payment_details'] or 'Sin referencia',
    }]
    totals = [{
        'Artículos': detail['unit_count'],
        'Productos distintos': detail['distinct_product_count'],
        'Total (MXN)': detail['total'],
    }]
    return (
        ('Datos de la venta', operation),
        ('Productos', list(detail['items'])),
        ('Totales', totals),
    )
