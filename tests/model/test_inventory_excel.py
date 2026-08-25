import unittest
from types import SimpleNamespace

from openpyxl import load_workbook
from io import BytesIO
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from model.entity.models import AuditLog, Base, Product, StockMovement
from model.inventory_excel import (
    ACTION_ADD, ACTION_CREATE, ACTION_REPLACE, build_import_preview,
    canonical_inventory_value, generate_inventory_template, inventory_field_options,
    read_inventory_workbook, validate_import_rows,
)
from model.repository.product import ProductRepository


def product(product_id=1, name='Lápiz', barcode='750001',
            category='Papelería', supplier='Grupo ECCOS'):
    return SimpleNamespace(
        id=product_id, name=name, barcode=barcode,
        category=category, supplier=supplier)


def valid_row(**changes):
    row = {
        'Nombre': 'Cuaderno', 'Descripción': 'Cuaderno profesional',
        'Código de barras': '750002', 'Precio de costo': '20.00',
        'Precio de venta': '40.00', 'Cantidad disponible': '10',
        'Categoría': 'Papelería', 'Proveedor': 'ECCOS', 'Existencia mínima': '3',
        'Acción': ACTION_CREATE,
    }
    row.update(changes)
    return row


class InventoryExcelTest(unittest.TestCase):

    def test_inventory_options_collapse_case_accents_and_spaces(self):
        products = [
            product(1, category='Papelería', supplier='Grupo ECCOS'),
            product(2, category=' papeleria ', supplier='grupo eccos'),
            product(3, category='Bebidas', supplier='Distribuidora Norte'),
        ]

        self.assertEqual(inventory_field_options(products, 'category'),
                         ('Bebidas', 'Papelería'))
        self.assertEqual(canonical_inventory_value(' PAPELERIA ', ('Papelería',)),
                         'Papelería')

    def test_excel_reuses_registered_category_and_supplier(self):
        row = valid_row(**{
            'Categoría': ' papeleria ', 'Proveedor': 'grupo eccos',
        })

        plans, errors = validate_import_rows([row], [product()])

        self.assertFalse(errors)
        self.assertEqual(plans[0]['category'], 'Papelería')
        self.assertEqual(plans[0]['supplier'], 'Grupo ECCOS')

    def test_template_can_be_read_after_adding_a_product(self):
        workbook = load_workbook(BytesIO(generate_inventory_template()))
        workbook['Inventario'].append((
            'Cuaderno', 'Cuaderno profesional', '00750002', 20, 40, 10,
            'Papelería', 'ECCOS', 3))
        output = BytesIO()
        workbook.save(output)

        rows = read_inventory_workbook(output.getvalue())

        self.assertEqual(rows[0]['Nombre'], 'Cuaderno')
        self.assertEqual(rows[0]['Código de barras'], '00750002')

    def test_existing_product_defaults_to_add_stock(self):
        rows = [valid_row(**{'Nombre': 'Lápiz', 'Código de barras': '750001'})]

        preview = build_import_preview(rows, [product()])

        self.assertEqual(preview[0]['Acción'], ACTION_ADD)
        self.assertIn('Existente', preview[0]['Estado'])

    def test_duplicate_barcode_inside_file_is_rejected(self):
        first = valid_row()
        second = valid_row(**{'Nombre': 'Cuaderno grande'})

        plans, errors = validate_import_rows([first, second], [])

        self.assertEqual(len(plans), 1)
        self.assertTrue(any('código de barras está repetido' in error for error in errors))

    def test_existing_product_can_replace_stock(self):
        row = valid_row(**{
            'Nombre': 'Lápiz', 'Código de barras': '750001',
            'Acción': ACTION_REPLACE,
        })

        plans, errors = validate_import_rows([row], [product()])

        self.assertFalse(errors)
        self.assertEqual(plans[0]['existing_id'], 1)
        self.assertEqual(plans[0]['quantity'], 10)

    def test_required_fields_are_validated(self):
        plans, errors = validate_import_rows([valid_row(**{'Categoría': ''})], [])

        self.assertFalse(plans)
        self.assertTrue(any('categoría son obligatorios' in error for error in errors))

    def test_repository_import_creates_products_and_audit_in_one_commit(self):
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        session = Session(engine)
        repository = ProductRepository(session)
        plans, errors = validate_import_rows([valid_row()], [])
        self.assertFalse(errors)

        result = repository.import_inventory(plans, 'Administrador')

        self.assertEqual(result['created'], 1)
        self.assertEqual(session.scalar(select(func.count(Product.id))), 1)
        self.assertEqual(session.scalar(select(func.count(AuditLog.id))), 1)
        self.assertEqual(session.scalar(select(func.count(StockMovement.id))), 0)
        session.close()


if __name__ == '__main__':
    unittest.main()
