"""Impresión directa de tickets ESC/POS mediante la cola de Windows."""

import ctypes
import textwrap
from ctypes import wintypes
from datetime import datetime


ESC = b'\x1b'
GS = b'\x1d'


def _text(value) -> bytes:
    """Codifica texto para impresoras térmicas genéricas sin romper el trabajo."""
    return str(value or '').encode('cp850', errors='replace')


def _lines(value, columns):
    result = []
    for paragraph in str(value or '').splitlines() or ['']:
        result.extend(textwrap.wrap(
            paragraph, width=columns, break_long_words=True,
            break_on_hyphens=False, replace_whitespace=True,
        ) or [''])
    return result


def build_escpos_ticket(
        business: dict, folio: str, created_at, items, payment_method: str,
        payment_details: str = '', customer: str = '', paper_width_mm: int = 58,
        ticket_title: str = 'TICKET DE VENTA', barcode: str = '') -> bytes:
    """Construye un ticket que avanza solamente las líneas que contiene."""
    if paper_width_mm not in (58, 80):
        raise ValueError('El ancho de ticket debe ser 58 u 80 mm.')
    columns = 32 if paper_width_mm == 58 else 48
    separator = '-' * columns
    output = bytearray(ESC + b'@')  # inicializar

    def command(value):
        output.extend(value)

    def line(value=''):
        output.extend(_text(value) + b'\n')

    def wrapped(value):
        for value_line in _lines(value, columns):
            line(value_line)

    command(ESC + b'a\x01')  # centrado
    command(ESC + b'E\x01')
    wrapped(business.get('business_name') or 'Mi negocio')
    command(ESC + b'E\x00')
    for value in (
        business.get('slogan'), business.get('legal_name'),
        business.get('receipt_header'), business.get('address'),
        ', '.join(filter(None, (
            business.get('city'), business.get('state'), business.get('postal_code')))),
        f"Tel: {business.get('phone')}" if business.get('phone') else '',
        f"RFC: {business.get('tax_id')}" if business.get('tax_id') else '',
    ):
        if value:
            wrapped(value)

    if barcode:
        barcode_data = ('{B' + str(barcode).strip().upper()).encode(
            'ascii', errors='ignore')
        if len(barcode_data) <= 255:
            command(ESC + b'a\x01')
            command(GS + b'H\x02')  # texto legible debajo
            command(GS + b'h\x3c')
            command(GS + b'w\x02')
            command(GS + b'k\x49' + bytes((len(barcode_data),)) + barcode_data)
            line()
    line(separator)
    command(ESC + b'E\x01')
    wrapped(ticket_title)
    wrapped(f'Folio: {folio}')
    command(ESC + b'E\x00')
    timestamp = (created_at.strftime('%d/%m/%Y %H:%M')
                 if isinstance(created_at, datetime) else str(created_at))
    wrapped(timestamp)
    if customer:
        wrapped(f'Cliente: {customer}')
    line(separator)

    command(ESC + b'a\x00')  # izquierda
    total = 0.0
    for item in items:
        quantity = max(1, int(item['quantity']))
        unit_price = float(item['unit_price'])
        line_total = quantity * unit_price
        total += line_total
        command(ESC + b'E\x01')
        wrapped(item.get('name') or 'Artículo')
        command(ESC + b'E\x00')
        wrapped(f'{quantity} x ${unit_price:,.2f} MXN')
        amount = f'${line_total:,.2f}'
        line(amount.rjust(columns))
    line(separator)
    command(ESC + b'E\x01')
    total_amount = f'${total:,.2f} MXN'
    line(f"TOTAL{total_amount.rjust(max(1, columns - 5))}")
    command(ESC + b'E\x00')
    line(separator)

    command(ESC + b'a\x01')
    command(ESC + b'E\x01')
    wrapped(f'Pago: {payment_method or "No especificado"}')
    command(ESC + b'E\x00')
    for detail in str(payment_details or '').split('|'):
        if detail.strip():
            wrapped(detail.strip())
    line(separator)
    for value in (
        business.get('receipt_footer') or 'Gracias por su compra.',
        business.get('return_policy'),
        'Comprobante de venta - Puntos ECCOS',
        'MXN - No sustituye factura fiscal',
    ):
        if value:
            wrapped(value)

    command(b'\n\n\n')       # avance mínimo para corte manual o automático
    command(GS + b'V\x00')    # corte completo; se ignora si el equipo no tiene cuchilla
    return bytes(output)


def default_printer_name() -> str:
    """Obtiene la impresora predeterminada del usuario actual de Windows."""
    if not hasattr(ctypes, 'WinDLL'):
        raise RuntimeError('La impresión directa solamente está disponible en Windows.')
    winspool = ctypes.WinDLL('winspool.drv', use_last_error=True)
    size = wintypes.DWORD()
    winspool.GetDefaultPrinterW(None, ctypes.byref(size))
    if not size.value:
        raise RuntimeError('Windows no tiene una impresora predeterminada configurada.')
    buffer = ctypes.create_unicode_buffer(size.value)
    if not winspool.GetDefaultPrinterW(buffer, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    return buffer.value


def print_raw_ticket(data: bytes, document_name='Ticket Puntos ECCOS') -> str:
    """Envía una sola copia RAW a la impresora predeterminada de Windows."""
    printer_name = default_printer_name()
    virtual_printers = ('print to pdf', 'xps', 'onenote', 'fax')
    if any(name in printer_name.casefold() for name in virtual_printers):
        raise RuntimeError(
            f'La impresora predeterminada es "{printer_name}". Configura una '
            'impresora térmica compatible con ESC/POS como predeterminada en Windows.')
    winspool = ctypes.WinDLL('winspool.drv', use_last_error=True)

    class DOC_INFO_1W(ctypes.Structure):
        _fields_ = [
            ('pDocName', wintypes.LPWSTR),
            ('pOutputFile', wintypes.LPWSTR),
            ('pDatatype', wintypes.LPWSTR),
        ]

    handle = wintypes.HANDLE()
    if not winspool.OpenPrinterW(printer_name, ctypes.byref(handle), None):
        raise ctypes.WinError(ctypes.get_last_error())
    job_started = page_started = False
    try:
        document = DOC_INFO_1W(document_name, None, 'RAW')
        if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(document)):
            raise ctypes.WinError(ctypes.get_last_error())
        job_started = True
        if not winspool.StartPagePrinter(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        page_started = True
        written = wintypes.DWORD()
        raw_data = ctypes.create_string_buffer(data)
        if not winspool.WritePrinter(handle, raw_data, len(data), ctypes.byref(written)):
            raise ctypes.WinError(ctypes.get_last_error())
        if written.value != len(data):
            raise RuntimeError('Windows no envió el ticket completo a la impresora.')
    finally:
        if page_started:
            winspool.EndPagePrinter(handle)
        if job_started:
            winspool.EndDocPrinter(handle)
        winspool.ClosePrinter(handle)
    return printer_name
