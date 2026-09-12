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
                'Cliente nuevo', '9930000000', 'cliente@example.com', '', 'Alta desde caja')

        self.assertEqual(customer.name, 'Cliente nuevo')
        self.assertEqual(repository.get_customers()[0].phone, '9930000000')

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
