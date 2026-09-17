from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from model.sales_history import build_sale_detail, sale_detail_pdf_sections
from model.report.exports import generate_pdf_bytes


def _sale(sale_id, product_id, name, price, *, created_at=None):
    return SimpleNamespace(
        id=sale_id,
        product_id=product_id,
        product_name=name,
        product=None,
        price=SimpleNamespace(amount=Decimal(str(price))),
        date=date(2026, 9, 17),
        created_at=created_at or datetime(2026, 9, 17, 13, 42, 17),
        transaction_id='transaction-123',
        payment_method='Efectivo',
        payment_details='Recibido: $100.00 | Cambio: $6.00',
        customer='Público general',
        cashier='admin',
        register_name='Caja principal',
        status='Completada',
    )


@pytest.mark.unit
def test_build_sale_detail_groups_lines_and_keeps_exact_sale_time():
    detail = build_sale_detail([
        _sale(9, 2, 'Agua mineral', '16.00'),
        _sale(7, 1, 'Café', '39.00'),
        _sale(8, 1, 'Café', '39.00'),
    ])

    assert detail['first_sale_id'] == 7
    assert detail['date_label'] == '17/09/2026'
    assert detail['time_label'] == '13:42:17'
    assert detail['unit_count'] == 3
    assert detail['total'] == pytest.approx(94.0)
    assert detail['items'] == (
        {
            'Producto': 'Café',
            'Cantidad': 2,
            'Precio unitario': 39.0,
            'Importe': 78.0,
        },
        {
            'Producto': 'Agua mineral',
            'Cantidad': 1,
            'Precio unitario': 16.0,
            'Importe': 16.0,
        },
    )


@pytest.mark.unit
def test_build_sale_detail_does_not_merge_different_unit_prices():
    detail = build_sale_detail([
        _sale(1, 1, 'Café', '39.00'),
        _sale(2, 1, 'Café', '35.00'),
    ])

    assert len(detail['items']) == 2
    assert [item['Precio unitario'] for item in detail['items']] == [39.0, 35.0]
    assert detail['total'] == pytest.approx(74.0)


@pytest.mark.unit
def test_sale_detail_pdf_sections_include_operation_metadata_and_totals():
    detail = build_sale_detail([_sale(7, 1, 'Café', '39.00')])

    sections = sale_detail_pdf_sections(detail, 'V-000007')

    assert sections[0] == ('Datos de la venta', [{
        'Folio': 'V-000007',
        'Fecha': '17/09/2026',
        'Hora': '13:42:17',
        'Estado': 'Completada',
        'Método de pago': 'Efectivo',
        'Cliente': 'Público general',
        'Responsable': 'admin',
        'Caja': 'Caja principal',
        'Detalle del pago': 'Recibido: $100.00 | Cambio: $6.00',
    }])
    assert sections[1][0] == 'Productos'
    assert sections[2] == ('Totales', [{
        'Artículos': 1,
        'Productos distintos': 1,
        'Total (MXN)': 39.0,
    }])


@pytest.mark.unit
def test_build_sale_detail_rejects_an_empty_operation():
    with pytest.raises(ValueError, match='venta vacía'):
        build_sale_detail([])


@pytest.mark.integration
def test_sale_detail_sections_generate_an_independent_a4_pdf():
    detail = build_sale_detail([_sale(7, 1, 'Café', '39.00')])

    document = generate_pdf_bytes(
        {'business_name': 'Puntos ECCOS'},
        'Detalle de venta V-000007',
        'Venta realizada el 17/09/2026 a las 13:42:17',
        sale_detail_pdf_sections(detail, 'V-000007'),
    )

    assert document.startswith(b'%PDF-')
    assert len(document) > 1_000
