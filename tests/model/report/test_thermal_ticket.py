import unittest
from io import BytesIO

from pypdf import PdfReader
from reportlab.lib.units import mm

from model.report.ticket import generate_thermal_ticket_bytes


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
            self.assertGreater(float(page.mediabox.height), 80 * mm)

    def test_rejects_non_thermal_width(self):
        with self.assertRaises(ValueError):
            self._ticket(76)


if __name__ == '__main__':
    unittest.main()
