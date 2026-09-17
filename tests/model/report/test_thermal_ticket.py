import unittest
from io import BytesIO
from unittest.mock import patch

from pypdf import PdfReader
from reportlab.lib.units import mm

from model.report.ticket import generate_thermal_ticket_bytes
from model.report.thermal_printer import (
    build_escpos_ticket, direct_printing_available, print_raw_ticket,
)


class ThermalTicketTest(unittest.TestCase):
    BUSINESS = {
        'business_name': 'Grupo ECCOS', 'legal_name': 'Grupo ECCOS',
        'receipt_header': 'Comprobante de mostrador',
        'receipt_footer': 'Gracias por su compra.', 'return_policy': 'Conserva tu ticket.',
    }
    ITEMS = (
        {'name': 'Audífonos inalámbricos azules', 'quantity': 3, 'unit_price': 230.0},
        {'name': 'Cable USB', 'quantity': 1, 'unit_price': 75.5},
    )

    def _ticket(self, width):
        return generate_thermal_ticket_bytes(
            self.BUSINESS, 'V-000001', '25/08/2026 16:45', self.ITEMS,
            'Efectivo', 'Recibido: $800.00 MXN | Cambio: $34.50 MXN',
            'Público general', width)

    def test_generates_valid_58_and_80_mm_pdf(self):
        for width in (58, 80):
            data = self._ticket(width)
            self.assertTrue(data.startswith(b'%PDF-'))
            page = PdfReader(BytesIO(data)).pages[0]
            self.assertAlmostEqual(float(page.mediabox.width), width * mm, delta=.5)
            self.assertGreater(float(page.mediabox.height), 70 * mm)
            self.assertLess(float(page.mediabox.height), 105 * mm)

    def test_rejects_non_thermal_width(self):
        with self.assertRaises(ValueError):
            self._ticket(76)

    def test_height_grows_with_the_complete_sale_detail(self):
        short_page = PdfReader(BytesIO(self._ticket(58))).pages[0]
        long_items = self.ITEMS + tuple({
            'name': f'Producto adicional {number} con una descripción extensa',
            'quantity': number,
            'unit_price': 10.0,
        } for number in range(1, 11))
        long_data = generate_thermal_ticket_bytes(
            self.BUSINESS, 'V-000002', '25/08/2026 16:50', long_items,
            'Efectivo', 'Recibido: $1,000.00 MXN | Cambio: $0.00 MXN',
            'Público general', 58)
        long_page = PdfReader(BytesIO(long_data)).pages[0]

        self.assertGreater(
            float(long_page.mediabox.height),
            float(short_page.mediabox.height) + 100 * mm,
        )

    def test_direct_ticket_uses_line_feed_and_one_cut(self):
        data = build_escpos_ticket(
            self.BUSINESS, 'V-000001', '25/08/2026 16:45', self.ITEMS,
            'Efectivo', 'Recibido: $800.00 MXN | Cambio: $34.50 MXN',
            'Público general', 58)

        self.assertTrue(data.startswith(b'\x1b@'))
        self.assertEqual(data.count(b'\x1dV\x00'), 1)
        self.assertNotIn(b'\x0c', data)
        self.assertIn(b'V-000001', data)

    def test_direct_voucher_includes_a_scannable_code128(self):
        data = build_escpos_ticket(
            self.BUSINESS, 'VALE-1234-5678-ABCD-EF01', '25/08/2026 16:45',
            ({'name': 'Saldo a favor', 'quantity': 1, 'unit_price': 500.0},),
            'VALE DE SALDO A FAVOR', paper_width_mm=58,
            ticket_title='VALE DE SALDO A FAVOR',
            barcode='VALE-1234-5678-ABCD-EF01')

        self.assertIn(b'\x1dk\x49', data)
        self.assertIn(b'{BVALE-1234-5678-ABCD-EF01', data)

    @patch('model.report.thermal_printer.default_printer_name',
           return_value='Microsoft Print to PDF')
    def test_direct_print_rejects_a_virtual_default_printer(self, _default):
        with self.assertRaisesRegex(RuntimeError, 'impresora térmica'):
            print_raw_ticket(b'ticket')

    def test_direct_print_availability_matches_the_runtime_platform(self):
        """Cloud Linux must not expose a Windows-only printer action."""
        import ctypes

        self.assertEqual(direct_printing_available(), hasattr(ctypes, 'WinDLL'))


if __name__ == '__main__':
    unittest.main()
