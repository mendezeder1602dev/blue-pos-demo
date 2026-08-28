"""Escenarios QA integrales para ventas, vales, devoluciones y caja.

Todas las pruebas usan SQLite en memoria: nunca escriben en la base operativa.
Los ``expectedFailure`` documentan huecos conocidos que deben convertirse en
pruebas normales al implementar la regla correspondiente.
"""

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from model.authorization import authorization_context
from model.entity.models import (
    Base, CashClose, CashMovement, CashOpening, Product, Sale,
    StoreCreditMovement, StoreCreditVoucher,
)
from model.repository.cash_close import CashCloseRepository
from model.repository.cash_control import CashControlRepository
from model.repository.sale import SaleFilter, SaleRepository
from model.timezone import mexico_today
from model.util.monetary_types import CUPMoney


class TestPOSEndToEndQA(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.sales = SaleRepository(self.session)
        self.cash = CashControlRepository(self.session)
        self.closes = CashCloseRepository(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def product(self, name='Producto QA', price=100.0, quantity=10):
        product = Product(
            name=name, description='Prueba integral',
            price=CUPMoney(f'{price:.2f}'), cost=CUPMoney('40.00'),
            quantity=quantity, is_active=True,
        )
        self.session.add(product)
        self.session.commit()
        return product

    def sale(self, product, method='Efectivo', details=''):
        return Sale(
            product_id=product.id, product_name=product.name,
            date=mexico_today(), price=product.price, cost=product.cost,
            payment_method=method, payment_details=details,
            cashier='Vendedor QA', customer='Cliente QA',
        )

    def voucher(self, amount, code='VALE-QA01-QA02-QA03-QA04'):
        voucher = StoreCreditVoucher(
            code=code, original_transaction_id='devolucion-qa',
            initial_amount=CUPMoney(f'{amount:.2f}'),
            balance=CUPMoney(f'{amount:.2f}'), status='Activo',
            customer='Cliente QA', reason='Devolución QA', issued_by='Administrador',
        )
        self.session.add(voucher)
        self.session.commit()
        return voucher

    def opening(self, amount=500.0, limit=3000.0):
        return self.cash.open_day(CashOpening(
            date=mexico_today(), opening_amount=CUPMoney(f'{amount:.2f}'),
            cash_limit=CUPMoney(f'{limit:.2f}'), opened_by='Administrador',
            shift_responsible='Vendedor QA',
        ), 'superuser')

    def test_voucher_equal_to_purchase_is_exhausted_without_replacement(self):
        product = self.product(price=100.0)
        voucher = self.voucher(100.0)
        inserted = self.sales.insert_transaction(
            [(self.sale(product, 'Vale', 'Aplicado: $100.00 MXN'), 1)],
            voucher.code, 100.0, 'Vendedor QA')

        self.session.refresh(voucher)
        replacements = self.session.scalars(select(StoreCreditVoucher).where(
            StoreCreditVoucher.original_transaction_id == inserted[0].transaction_id,
            StoreCreditVoucher.id != voucher.id,
        )).all()
        self.assertEqual(voucher.status, 'Agotado')
        self.assertEqual(float(voucher.balance.amount), 0.0)
        self.assertEqual(replacements, [])

    def test_voucher_greater_than_purchase_creates_one_replacement(self):
        product = self.product(price=100.0)
        voucher = self.voucher(175.25)
        inserted = self.sales.insert_transaction(
            [(self.sale(product, 'Vale', 'Aplicado: $100.00 MXN'), 1)],
            voucher.code, 100.0, 'Vendedor QA')

        replacements = self.session.scalars(select(StoreCreditVoucher).where(
            StoreCreditVoucher.original_transaction_id == inserted[0].transaction_id,
            StoreCreditVoucher.id != voucher.id,
        )).all()
        self.assertEqual(len(replacements), 1)
        self.assertEqual(float(replacements[0].balance.amount), 75.25)
        self.assertNotEqual(replacements[0].code, voucher.code)

    def test_smaller_voucher_supports_cash_complement_without_replacement(self):
        product = self.product(price=100.0)
        voucher = self.voucher(60.0)
        inserted = self.sales.insert_transaction([(
            self.sale(product, 'Vale + Efectivo',
                      'Aplicado: $60.00 MXN | Complemento en efectivo: $40.00 MXN'), 1,
        )], voucher.code, 60.0, 'Vendedor QA')

        self.session.refresh(voucher)
        self.assertEqual(inserted[0].payment_method, 'Vale + Efectivo')
        self.assertEqual(voucher.status, 'Agotado')
        self.assertEqual(self.session.scalar(select(StoreCreditVoucher).where(
            StoreCreditVoucher.original_transaction_id == inserted[0].transaction_id,
            StoreCreditVoucher.id != voucher.id,
        )), None)

    def test_invalid_voucher_rolls_back_sale_and_inventory(self):
        product = self.product(price=100.0, quantity=3)
        with self.assertRaises(ValueError):
            self.sales.insert_transaction(
                [(self.sale(product, 'Vale'), 1)], 'VALE-INEXISTENTE', 100.0, 'Vendedor QA')

        self.session.refresh(product)
        self.assertEqual(product.quantity, 3)
        self.assertEqual(self.session.scalars(select(Sale)).all(), [])

    def test_old_code_cannot_be_reused_after_rollover(self):
        first = self.product('Producto uno', 100.0)
        second = self.product('Producto dos', 50.0)
        voucher = self.voucher(150.0)
        self.sales.insert_transaction(
            [(self.sale(first, 'Vale'), 1)], voucher.code, 100.0, 'Vendedor QA')

        with self.assertRaises(ValueError):
            self.sales.insert_transaction(
                [(self.sale(second, 'Vale'), 1)], voucher.code, 50.0, 'Vendedor QA')

    def test_same_unit_cannot_be_returned_twice(self):
        product = self.product(price=100.0)
        sold = self.sales.insert_transaction([(self.sale(product), 1)])[0]
        plan = [{'sale_ids': [sold.id], 'disposition': 'Reintegrar a inventario'}]
        with authorization_context('superuser'):
            self.sales.return_items(
                sold.transaction_id, plan, 'Primera devolución QA', 'Efectivo')
            with self.assertRaises(ValueError):
                self.sales.return_items(
                    sold.transaction_id, plan, 'Segunda devolución QA', 'Efectivo')

    def test_security_withdrawal_cannot_exceed_available_cash(self):
        self.opening(amount=500.0)
        with self.assertRaises(ValueError):
            self.cash.add_movement(CashMovement(
                date=mexico_today(), movement_type='Retiro',
                amount=CUPMoney('501.00'), reason='Retiro QA',
                authorized_by='Administrador',
            ), 'superuser', available_cash=500.0)

    def test_seller_cannot_authorize_security_withdrawal(self):
        self.opening(amount=500.0)
        with self.assertRaises(PermissionError):
            self.cash.add_movement(CashMovement(
                date=mexico_today(), movement_type='Retiro',
                amount=CUPMoney('100.00'), reason='Retiro QA',
                authorized_by='Vendedor',
            ), 'store', available_cash=500.0)

    def test_same_shift_cannot_be_closed_twice(self):
        opening = self.opening()
        self.closes.insert(CashClose(
            date=mexico_today(), opening_id=opening.id, cashier='Administrador'))
        with self.assertRaises(ValueError):
            self.closes.insert(CashClose(
                date=mexico_today(), opening_id=opening.id, cashier='Administrador'))

    def test_sale_repository_rejects_sale_without_open_shift(self):
        product = self.product(price=100.0)
        strict_sales = SaleRepository(self.session, enforce_open_cash=True)
        with self.assertRaises(ValueError):
            strict_sales.insert_transaction([(self.sale(product), 1)])

    def test_reverse_voucher_sale_restores_customer_credit_with_new_code(self):
        product = self.product(price=100.0)
        voucher = self.voucher(100.0)
        sold = self.sales.insert_transaction(
            [(self.sale(product, 'Vale'), 1)], voucher.code, 100.0, 'Vendedor QA')[0]
        with authorization_context('superuser'):
            self.sales.reverse_transaction(sold.transaction_id, 'Anulación QA válida', 'Administrador')

        restored = self.session.scalar(select(StoreCreditVoucher).where(
            StoreCreditVoucher.original_transaction_id == sold.transaction_id,
            StoreCreditVoucher.reason.like('Crédito restituido por anulación:%'),
        ))
        self.assertIsNotNone(restored)
        self.assertNotEqual(restored.code, voucher.code)
        self.assertEqual(restored.status, 'Activo')
        self.assertEqual(float(restored.balance.amount), 100.0)

    def test_cash_refund_creates_current_cash_outflow(self):
        self.opening()
        product = self.product(price=100.0)
        strict_sales = SaleRepository(self.session, enforce_open_cash=True)
        sold = strict_sales.insert_transaction([(self.sale(product, 'Efectivo'), 1)])[0]
        with authorization_context('superuser'):
            strict_sales.return_items(
                sold.transaction_id,
                [{'sale_ids': [sold.id], 'disposition': 'Reintegrar a inventario'}],
                'Reembolso efectivo QA', 'Efectivo')

        refunds = self.session.scalars(select(CashMovement).where(
            CashMovement.movement_type == 'Retiro')).all()
        self.assertEqual(len(refunds), 1)
        self.assertEqual(float(refunds[0].amount.amount), 100.0)

    def test_replacement_value_must_equal_returned_value(self):
        sold_product = self.product('Producto vendido', 100.0, quantity=5)
        replacement = self.product('Producto reemplazo', 100.0, quantity=5)
        sold = self.sales.insert_transaction([(self.sale(sold_product), 2)])
        with authorization_context('superuser'):
            with self.assertRaises(ValueError):
                self.sales.return_items(
                    sold[0].transaction_id,
                    [{'sale_ids': [line.id for line in sold],
                      'disposition': 'Reintegrar a inventario'}],
                    'Cambio de valor desigual', 'Cambio',
                    replacement_product_id=replacement.id, replacement_quantity=1)

    def test_withdrawal_does_not_trust_missing_external_cash_total(self):
        self.opening(amount=500.0)
        with self.assertRaises(ValueError):
            self.cash.add_movement(CashMovement(
                date=mexico_today(), movement_type='Retiro',
                amount=CUPMoney('5000.00'), reason='Retiro sin saldo calculado',
                authorized_by='Administrador',
            ), 'superuser', available_cash=None)

    def test_cash_close_repository_enforces_admin_role(self):
        opening = self.opening()
        with authorization_context('store'):
            with self.assertRaises(PermissionError):
                self.closes.insert(CashClose(
                    date=mexico_today(), opening_id=opening.id, cashier='Vendedor'))


if __name__ == '__main__':
    unittest.main()
