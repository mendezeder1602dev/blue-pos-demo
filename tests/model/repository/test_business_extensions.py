import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.authorization import authorization_context
from model.database_utilities import backup_database_bytes, restore_database_bytes
from model.entity.models import Base, Customer, Product
from model.repository.operations import OperationsRepository
from model.repository.purchase_order import PurchaseOrderRepository
from model.util.monetary_types import CUPMoney


class TestBusinessExtensions(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)

    def tearDown(self):
        self.session.close(); self.engine.dispose()

    def test_incident_lifecycle_is_persistent_and_audited(self):
        repository = OperationsRepository(self.session)
        incident = repository.create_incident(
            'Caja', 'Diferencia de corte', 'Revisar efectivo', 'Alta', 'Admin')
        repository.update_incident(
            incident.id, 'Resuelta', 'Admin', 'Conteo validado', 'Admin')
        self.assertEqual(repository.get_incidents()[0].status, 'Resuelta')
        self.assertEqual(repository.get_audit_logs()[0].event_type,
                         'incidencia_actualizada')

    def test_purchase_receipt_updates_stock_and_average_cost(self):
        product = Product(name='Café', description='Bolsa', price=CUPMoney('30.00'),
                          cost=CUPMoney('10.00'), quantity=10)
        self.session.add(product); self.session.commit()
        repository = PurchaseOrderRepository(self.session)
        order = repository.create('Proveedor', [{
            'product_id': product.id, 'quantity': 10, 'unit_cost': 14,
        }], None, '', 'Admin')
        repository.receive(order.id, 'Admin')
        self.assertEqual(product.quantity, 20)
        self.assertEqual(float(product.cost.amount), 12.0)
        self.assertEqual(order.status, 'Recibida')

    def test_restore_rejects_non_sqlite_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            url = f"sqlite:///{Path(folder) / 'data.db'}"
            create_engine(url).dispose()
            with self.assertRaises(ValueError):
                restore_database_bytes(url, b'not-a-database')

    def test_customer_purchase_accumulates_points_and_spend(self):
        customer = Customer(name='Cliente frecuente')
        self.session.add(customer)
        self.session.commit()
        earned = OperationsRepository(self.session).record_customer_purchase(
            customer.name, 125.50, 'ticket-1', 'Admin')
        self.assertEqual(earned, 12)
        self.assertEqual(customer.loyalty_points, 12)
        self.assertEqual(float(customer.lifetime_spend.amount), 125.50)

    def test_seller_can_register_customer_for_credit_sale(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            customer = repository.add_customer(
                'Cliente nuevo', '9930000000', 'cliente@example.com', '',
                'Alta desde caja', address='Av. Principal 123')

        self.assertEqual(customer.name, 'Cliente nuevo')
        self.assertEqual(repository.get_customers()[0].phone, '+529930000000')
        self.assertEqual(customer.address, 'Av. Principal 123')

    def test_credit_customer_requires_phone_and_address(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            with self.assertRaisesRegex(ValueError, 'teléfono'):
                repository.add_customer(
                    'Sin teléfono', '', address='Av. Principal 123')
            with self.assertRaisesRegex(ValueError, 'dirección'):
                repository.add_customer('Sin dirección', '9930000000')

    def test_customer_fields_reject_values_longer_than_storage_limits(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            with self.assertRaisesRegex(ValueError, '120'):
                repository.add_customer(
                    'X' * 121, '9930000000', address='Av. Principal 123')

    def test_customer_contact_is_validated_and_normalized_for_selected_country(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            customer = repository.add_customer(
                'Contacto mexicano', '993 123 4567', 'CLIENTE@GMAIL.COM', '', '',
                address='Av. Principal 123', phone_country='MX', postal_code='86000')

        self.assertEqual(customer.phone, '+529931234567')
        self.assertEqual(customer.phone_country, 'MX')
        self.assertEqual(customer.email, 'CLIENTE@gmail.com')
        self.assertEqual(customer.postal_code, '86000')

    def test_customer_rejects_phone_that_is_invalid_for_selected_country(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            with self.assertRaisesRegex(ValueError, 'M\u00e9xico'):
                repository.add_customer(
                    'Tel\u00e9fono inv\u00e1lido', '993123456', address='Av. Principal 123',
                    phone_country='MX')

    def test_customer_uses_phone_and_postal_rules_from_another_country(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            customer = repository.add_customer(
                'Contacto estadounidense', '202-555-0123',
                address='1600 Pennsylvania Ave', phone_country='US',
                postal_code='20500')

        self.assertEqual(customer.phone, '+12025550123')
        self.assertEqual(customer.phone_country, 'US')
        self.assertEqual(customer.postal_code, '20500')

    def test_customer_rejects_invalid_email_without_persisting_record(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            with self.assertRaisesRegex(ValueError, 'correo electr\u00f3nico v\u00e1lido'):
                repository.add_customer(
                    'Correo inv\u00e1lido', '9931234567', 'cliente@@correo',
                    address='Av. Principal 123', phone_country='MX')

        self.assertEqual(repository.get_customers(), [])

    def test_customer_rejects_invalid_postal_code_for_selected_country(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            with self.assertRaisesRegex(ValueError, 'c\u00f3digo postal'):
                repository.add_customer(
                    'C\u00f3digo inv\u00e1lido', '9931234567', address='Av. Principal 123',
                    phone_country='MX', postal_code='8600')

    def test_customer_search_matches_contact_and_address_fields(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            repository.add_customer(
                'María López', '9931112233', 'maria@example.com', '', '',
                address='Colonia Centro 45')
            repository.add_customer(
                'Juan Pérez', '9939998877', 'juan@example.com', '', '',
                address='Fraccionamiento Las Flores')

        self.assertEqual(
            [customer.name for customer in repository.search_customers('centro')],
            ['María López'])
        self.assertEqual(
            [customer.name for customer in repository.search_customers('9998')],
            ['Juan Pérez'])

    def test_seller_can_update_customer_contact_before_credit(self):
        repository = OperationsRepository(self.session)
        with authorization_context('seller'):
            customer = repository.add_customer(
                'Cliente editable', '9930000000', address='Dirección anterior')
            updated = repository.update_customer(
                customer.id, 'Cliente editable', '9930000001', 'Dirección actualizada',
                'cliente@example.com', '', 'Datos confirmados', 'Vendedor QA')

        self.assertEqual(updated.phone, '+529930000001')
        self.assertEqual(updated.address, 'Dirección actualizada')
        self.assertEqual(repository.get_audit_logs()[0].event_type, 'cliente_actualizado')

    def test_restore_replaces_database_with_valid_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.db'
            destination = Path(folder) / 'destination.db'
            for path, value in ((source, 'copia'), (destination, 'actual')):
                with closing(sqlite3.connect(path)) as connection:
                    connection.execute('CREATE TABLE marker (value TEXT)')
                    connection.execute('INSERT INTO marker VALUES (?)', (value,))
                    connection.commit()
            source_url = f'sqlite:///{source}'
            destination_url = f'sqlite:///{destination}'
            restore_database_bytes(destination_url, backup_database_bytes(source_url))
            with closing(sqlite3.connect(destination)) as connection:
                value = connection.execute('SELECT value FROM marker').fetchone()[0]
            self.assertEqual(value, 'copia')

    def test_seller_cannot_download_or_restore_the_complete_database(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'protected.db'
            with closing(sqlite3.connect(database)) as connection:
                connection.execute('CREATE TABLE marker (value TEXT)')
                connection.commit()
            url = f'sqlite:///{database}'

            with authorization_context('seller'):
                with self.assertRaises(PermissionError):
                    backup_database_bytes(url)
                with self.assertRaises(PermissionError):
                    restore_database_bytes(url, database.read_bytes())
