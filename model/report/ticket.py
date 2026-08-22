"""Generación de comprobantes de venta listos para imprimir."""

from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, PackageLoader, select_autoescape
from xhtml2pdf import pisa


def generate_ticket_pdf(business: dict, items: Iterable[dict], sale_ids: Iterable[int],
                        sale_date: date, ticket_title: str = 'COMPROBANTE DE VENTA',
                        payment_method: str = '', payment_details: str = '') -> Path:
    """Genera un PDF por operación y devuelve su ubicación local.

    Los importes se reciben como datos simples para que el comprobante pueda
    crearse sin reutilizar la sesión de SQLite desde otro hilo.
    """
    normalized_items = []
    total = 0.0
    for item in items:
        quantity = int(item['quantity'])
        unit_price = float(item['unit_price'])
        line_total = quantity * unit_price
        total += line_total
        normalized_items.append({
            'name': item['name'],
            'quantity': quantity,
            'unit_price': f'{unit_price:,.2f}',
            'line_total': f'{line_total:,.2f}',
        })

    sale_ids = list(sale_ids)
    ticket_number = '-'.join(str(sale_id) for sale_id in sale_ids)
    output_directory = Path.home() / '.blue-pos' / 'tickets'
    output_directory.mkdir(parents=True, exist_ok=True)
    file_name = f'ticket-{sale_date:%Y%m%d}-{ticket_number}.pdf'
    output_path = output_directory / file_name

    environment = Environment(
        loader=PackageLoader('model.report'),
        autoescape=select_autoescape(['html']),
    )
    html = environment.get_template('ticket.html').render(
        business=business,
        items=normalized_items,
        total=f'{total:,.2f}',
        sale_date=sale_date,
        created_at=datetime.now(),
        ticket_number=ticket_number,
        ticket_title=ticket_title,
        payment_method=payment_method,
        payment_details=payment_details,
    )

    with output_path.open('w+b') as pdf_file:
        result = pisa.CreatePDF(html, dest=pdf_file)
    if result.err:
        raise RuntimeError('No se pudo generar el ticket PDF.')
    return output_path
