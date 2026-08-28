import unittest

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from model.entity.models import (AuditLog, Base, HeldSale, Product,
                                 ReturnLossRequest, StockMovement)
from model.repository.operations import OperationsRepository
from model.util.monetary_types import CUPMoney


class TestOperationsRepository(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.repository = OperationsRepository(self.session)
        self.product = Product(
            name='Producto de control', description='Producto para operaciones',
            price=CUPMoney('20.00'), cost=CUPMoney('10.00'), quantity=10,
        )
        self.session.add(self.product)
        self.session.commit()

    def tearDown(self):
        self.session.execute(delete(HeldSale))
        self.session.execute(delete(ReturnLossRequest))
        self.session.execute(delete(StockMovement))
        self.session.execute(delete(AuditLog))
        self.session.execute(delete(Product).where(Product.id == self.product.id))
        self.session.commit()
        self.session.close()
        self.engine.dispose()

    def test_adjust_stock_creates_kardex_and_audit(self):
        self.repository.adjust_stock(
            self.product.id, 5, 'Entrada de compra', 'Recepción de proveedor',
            'Administrador', 'OC-001')

        self.assertEqual(self.product.quantity, 15)
        movement = self.repository.get_stock_movements()[0]
        self.assertEqual((movement.previous_stock, movement.resulting_stock), (10, 15))
        self.assertEqual(self.repository.get_audit_logs()[0].event_type, 'inventario_ajustado')

    def test_hold_sale_preserves_quantity_and_negotiated_price(self):
        held = self.repository.hold_sale(
            'Cliente en espera', '', 'Vendedor', {self.product.id: 2},
            {self.product.id: 17.50})

        self.assertEqual(held.items[0].quantity, 2)
        self.assertEqual(float(held.items[0].unit_price.amount), 17.50)
        self.repository.delete_held_sale(held.id)
        self.assertEqual(self.repository.get_held_sales(), [])

    def test_negative_result_is_rejected(self):
        with self.assertRaises(ValueError):
            self.repository.adjust_stock(
                self.product.id, -11, 'Merma o daño', 'Daño identificado', 'Administrador')

    def test_purchase_entry_can_update_weighted_average_cost(self):
        updated = self.repository.adjust_stock(
            self.product.id, 10, 'Entrada de compra', 'Recepción de proveedor',
            'Administrador', 'FAC-100', unit_cost=14,
            update_average_cost=True)

        self.assertEqual(updated.quantity, 20)
        self.assertEqual(float(updated.cost.amount), 12.00)
        self.assertIn('Costo $10.00 → $12.00 MXN',
                      self.repository.get_audit_logs()[0].detail)

    def test_merchandise_loss_cannot_register_purchase_cost(self):
        with self.assertRaises(ValueError):
            self.repository.adjust_stock(
                self.product.id, -1, 'Merma', 'Producto dañado', 'Administrador',
                unit_cost=10)

    def test_return_review_can_authorize_writeoff_without_reducing_sellable_stock(self):
        request = ReturnLossRequest(
            transaction_id='ticket-damaged', product_id=self.product.id,
            product_name=self.product.name, quantity=2, sale_ids='[]',
            concept='Producto dañado o no funciona', reason='No enciende',
            requested_by='Administrador')
        self.session.add(request)
        self.session.commit()

        resolved = self.repository.resolve_return_loss_request(
            request.id, 'Autorizar baja', 'Administrador', 'Daño confirmado')

        self.assertEqual(resolved.status, 'Baja autorizada')
        self.assertEqual(self.product.quantity, 10)
        movement = self.repository.get_stock_movements()[0]
        self.assertEqual(movement.quantity, 0)
        self.assertEqual(movement.movement_type, 'Baja por devolución')

    def test_return_review_can_reintegrate_verified_product(self):
        request = ReturnLossRequest(
            transaction_id='ticket-review', product_id=self.product.id,
            product_name=self.product.name, quantity=2, sale_ids='[]',
            concept='Otro · requiere revisión', reason='Revisión solicitada',
            requested_by='Administrador')
        self.session.add(request)
        self.session.commit()

        resolved = self.repository.resolve_return_loss_request(
            request.id, 'Reintegrar a inventario', 'Administrador',
            'Producto funcional y completo')

        self.assertEqual(resolved.status, 'Reintegrado')
        self.assertEqual(self.product.quantity, 12)


if __name__ == '__main__':
    unittest.main()
