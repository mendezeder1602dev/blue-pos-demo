"""Generación de comprobantes de venta listos para impresoras térmicas."""

import base64
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, PackageLoader, select_autoescape
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from xhtml2pdf import pisa
from model.timezone import mexico_now


THERMAL_WIDTHS = (58, 80)


def _wrap_ticket_text(text, font_name, font_size, available_width):
    """Divide texto por ancho real para que nunca salga del rollo."""
    paragraphs = str(text or '').splitlines() or ['']
    lines = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            lines.append('')
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f'{current} {word}'
            if stringWidth(candidate, font_name, font_size) <= available_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def generate_thermal_ticket_bytes(
        business: dict, folio: str, created_at, items: Iterable[dict],
        payment_method: str, payment_details: str = '', customer: str = '',
        paper_width_mm: int = 80, ticket_title: str = 'TICKET DE VENTA') -> bytes:
    """Genera un PDF de rollo térmico de 58 u 80 mm con altura automática.

    ``items`` recibe nombre, cantidad y precio unitario. El total se calcula aquí
    para que Venta y Venta exprés usen exactamente la misma lógica de impresión.
    """
    if paper_width_mm not in THERMAL_WIDTHS:
        raise ValueError('El ancho de ticket debe ser 58 u 80 mm.')
    normalized_items = []
    total = 0.0
    for item in items:
        quantity = max(1, int(item['quantity']))
        unit_price = float(item['unit_price'])
        line_total = quantity * unit_price
        total += line_total
        normalized_items.append({
            'name': str(item['name']).strip() or 'Artículo',
            'quantity': quantity, 'unit_price': unit_price, 'line_total': line_total,
        })

    page_width = paper_width_mm * mm
    margin = (3.2 if paper_width_mm == 58 else 4.0) * mm
    available = page_width - 2 * margin
    body_size = 7.2 if paper_width_mm == 58 else 8.2
    small_size = body_size - .8
    leading = body_size + 2.2
    header_lines = []
    for value in (
        business.get('legal_name'), business.get('receipt_header'),
        business.get('address'),
        ', '.join(filter(None, (business.get('city'), business.get('state'),
                                business.get('postal_code')))),
        f"Tel: {business.get('phone')}" if business.get('phone') else '',
        f"RFC: {business.get('tax_id')}" if business.get('tax_id') else '',
    ):
        if value:
            header_lines.extend(_wrap_ticket_text(value, 'Helvetica', small_size, available))
    detail_lines = []
    if payment_details:
        for detail in str(payment_details).split('|'):
            detail_lines.extend(_wrap_ticket_text(detail.strip(), 'Helvetica', small_size, available))
    footer_lines = []
    for value in (business.get('receipt_footer') or 'Gracias por su compra.',
                  business.get('return_policy')):
        if value:
            footer_lines.extend(_wrap_ticket_text(value, 'Helvetica', small_size, available))
    item_name_lines = sum(
        len(_wrap_ticket_text(item['name'], 'Helvetica-Bold', body_size, available))
        for item in normalized_items)
    estimated_lines = (16 + len(header_lines) + len(detail_lines) + len(footer_lines)
                       + item_name_lines + len(normalized_items) * 2)
    page_height = max(90 * mm, estimated_lines * leading + 18 * mm)

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(page_width, page_height), pageCompression=1)
    y = page_height - margin

    def centered(text, font='Helvetica', size=body_size, step=None):
        nonlocal y
        pdf.setFont(font, size)
        pdf.drawCentredString(page_width / 2, y, str(text))
        y -= step or (size + 2)

    def left(text, font='Helvetica', size=body_size, step=None):
        nonlocal y
        pdf.setFont(font, size)
        pdf.drawString(margin, y, str(text))
        y -= step or (size + 2)

    def right(text, font='Helvetica', size=body_size, step=None):
        nonlocal y
        pdf.setFont(font, size)
        pdf.drawRightString(page_width - margin, y, str(text))
        y -= step or (size + 2)

    def divider():
        nonlocal y
        y -= 2
        pdf.setLineWidth(.35)
        pdf.line(margin, y, page_width - margin, y)
        y -= 6

    logo_data = business.get('logo_data')
    if logo_data:
        try:
            image = ImageReader(BytesIO(base64.b64decode(logo_data)))
            logo_width = min(28 * mm, available * .55)
            logo_height = 12 * mm
            pdf.drawImage(image, (page_width - logo_width) / 2, y - logo_height,
                          width=logo_width, height=logo_height, preserveAspectRatio=True,
                          anchor='c', mask='auto')
            y -= logo_height + 3
        except (ValueError, TypeError, OSError):
            pass

    centered(business.get('business_name') or 'Mi negocio', 'Helvetica-Bold',
             11 if paper_width_mm == 58 else 13)
    if business.get('slogan'):
        for line in _wrap_ticket_text(
                business['slogan'], 'Helvetica', small_size, available):
            centered(line, size=small_size)
    for line in header_lines:
        centered(line, size=small_size)
    divider()
    centered(ticket_title, 'Helvetica-Bold', body_size + 1)
    centered(f'Folio: {folio}', 'Helvetica-Bold', body_size)
    timestamp = (created_at.strftime('%d/%m/%Y %H:%M')
                 if hasattr(created_at, 'strftime') else str(created_at))
    centered(timestamp, size=small_size)
    if customer:
        for line in _wrap_ticket_text(
                f'Cliente: {customer}', 'Helvetica', small_size, available):
            centered(line, size=small_size)
    divider()

    for item in normalized_items:
        for line in _wrap_ticket_text(item['name'], 'Helvetica-Bold', body_size, available):
            left(line, 'Helvetica-Bold', body_size)
        left(f"{item['quantity']} x ${item['unit_price']:,.2f} MXN", size=small_size,
             step=small_size + 1)
        right(f"${item['line_total']:,.2f}", 'Helvetica-Bold', body_size, step=leading)
    divider()
    pdf.setFont('Helvetica-Bold', body_size + 2)
    pdf.drawString(margin, y, 'TOTAL')
    pdf.drawRightString(page_width - margin, y, f'${total:,.2f} MXN')
    y -= body_size + 7
    divider()
    centered(f'Pago: {payment_method or "No especificado"}', 'Helvetica-Bold', body_size)
    for line in detail_lines:
        centered(line, size=small_size)
    divider()
    for line in footer_lines:
        centered(line, size=small_size)
    centered('Comprobante de venta · Puntos ECCOS', size=small_size)
    centered('MXN · No sustituye factura fiscal', size=small_size)
    y -= 5 * mm  # espacio de avance antes del corte físico de la impresora
    pdf.showPage()
    pdf.save()
    return output.getvalue()


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
        created_at=mexico_now(),
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
