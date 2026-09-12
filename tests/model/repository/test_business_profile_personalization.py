import unittest
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.entity.models import Base
from model.report.exports import (
    business_as_dict,
    generate_excel_bytes,
    generate_html_bytes,
    generate_pdf_bytes,
)
from model.repository.business_profile import BusinessProfileRepository


class TestBusinessProfilePersonalization(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.repository = BusinessProfileRepository(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_personalization_is_saved_and_exported(self):
        profile = self.repository.save_profile({
            'business_name': 'Grupo ECCOS', 'legal_name': 'Grupo ECCOS, S.A.',
            'business_type': 'Servicios', 'slogan': 'Soluciones que crecen contigo',
            'city': 'Puebla', 'state': 'Puebla', 'postal_code': '72000',
            'receipt_header': 'Sucursal Centro',
            'receipt_footer': 'Gracias por elegirnos.',
            'return_policy': 'Cambios dentro de 15 días.', 'brand_color': '#123B6D',
        })
        exported = business_as_dict(profile)
        self.assertEqual(exported['receipt_footer'], 'Gracias por elegirnos.')
        self.assertEqual(exported['city'], 'Puebla')
        pdf = generate_pdf_bytes(exported, 'Prueba', 'Documento de prueba',
                                 [('Datos', [{'Concepto': 'Total', 'Valor': '100 MXN'}])])
        self.assertTrue(pdf.startswith(b'%PDF'))

        excel = generate_excel_bytes(
            exported, 'Prueba', 'Documento de prueba',
            [('Datos', [{'Concepto': 'Total', 'Valor': '100 MXN'}])])
        workbook = load_workbook(BytesIO(excel), read_only=True)
        administrative_text = '\n'.join(
            str(cell.value or '') for row in workbook['Información'].iter_rows()
            for cell in row)
        self.assertNotIn('Gracias por elegirnos.', administrative_text)
        self.assertIn('Cambios dentro de 15 días.', administrative_text)

        html = generate_html_bytes(
            exported, 'Prueba <segura>', 'Documento de prueba',
            [('Datos', [{'Concepto': '<Total>', 'Valor': '100 MXN'}])]).decode('utf-8')
        self.assertIn('<!doctype html>', html)
        self.assertIn('Grupo ECCOS', html)
        self.assertIn('Datos', html)
        self.assertIn('&lt;Total&gt;', html)
        self.assertNotIn('<Total>', html)

    def test_unknown_profile_field_is_rejected(self):
        with self.assertRaises(ValueError):
            self.repository.save_profile({'campo_inseguro': 'valor'})

    def test_visual_profile_colors_are_saved_and_exported(self):
        profile = self.repository.save_profile({
            'business_name': 'Grupo ECCOS',
            'brand_color': '#0F766E',
            'app_background_color': '#F7F9FC',
            'app_surface_color': '#FFFFFF',
            'app_text_color': '#111820',
            'document_primary_color': '#FDE68A',
            'document_text_color': '#111820',
        })
        exported = business_as_dict(profile)
        self.assertEqual(exported['app_background_color'], '#F7F9FC')
        self.assertEqual(exported['document_primary_color'], '#FDE68A')

        html = generate_html_bytes(
            exported, 'Prueba', 'Documento de prueba',
            [('Datos', [{'Concepto': 'Total', 'Valor': '100 MXN'}])]).decode('utf-8')
        self.assertIn('--brand: #FDE68A', html)
        self.assertIn('--on-brand: #111820', html)

    def test_low_contrast_profile_colors_are_rejected(self):
        with self.assertRaises(ValueError):
            self.repository.save_profile({
                'app_background_color': '#FFFFFF',
                'app_surface_color': '#FFFFFF',
                'app_text_color': '#FFFFFF',
            })


if __name__ == '__main__':
    unittest.main()
