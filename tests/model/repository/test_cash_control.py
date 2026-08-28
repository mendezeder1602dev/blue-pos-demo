import json
import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.entity.models import Base, CashClose, CashMovement, CashOpening
from model.repository.cash_close import CashCloseRepository
from model.repository.cash_control import CashControlRepository
from model.timezone import mexico_today
from model.util.monetary_types import CUPMoney


class TestCashControlWorkflow(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_previous_close_can_seed_a_separate_opening(self):
        close_repository = CashCloseRepository(self.session)
        today = mexico_today()
        previous_date = today - timedelta(days=1)
        previous_close = close_repository.insert(CashClose(
            date=previous_date, cashier='Administrador',
            counted_cash=CUPMoney('1250.00'),
            denomination_details=json.dumps({'bill_500': 2, 'bill_200': 1, 'bill_50': 1}),
        ))

        latest = close_repository.get_latest_before(today)
        self.assertEqual(latest.id, previous_close.id)
        self.assertEqual(float(latest.counted_cash.amount), 1250.0)

        opening = CashControlRepository(self.session).open_day(CashOpening(
            date=today, opening_amount=latest.counted_cash,
            cash_limit=CUPMoney('3000.00'), opened_by='Administrador',
            denomination_details=latest.denomination_details,
            source_close_id=latest.id,
        ), 'superuser')
        self.assertEqual(opening.source_close_id, previous_close.id)
        self.assertEqual(float(opening.opening_amount.amount), 1250.0)

    def test_seller_cannot_confirm_opening(self):
        with self.assertRaises(PermissionError):
            CashControlRepository(self.session).open_day(CashOpening(
                date=mexico_today(), opening_amount=CUPMoney('500.00'),
                cash_limit=CUPMoney('3000.00'), opened_by='Vendedor',
            ), 'store')

    def test_multiple_shifts_can_open_and_close_on_same_day(self):
        control = CashControlRepository(self.session)
        closes = CashCloseRepository(self.session)
        today = mexico_today()

        first = control.open_day(CashOpening(
            date=today, opening_amount=CUPMoney('500.00'),
            cash_limit=CUPMoney('3000.00'), opened_by='Administrador',
            shift_responsible='Turno matutino',
        ), 'superuser')
        first_movement = control.add_movement(CashMovement(
            date=today, movement_type='Entrada', amount=CUPMoney('100.00'),
            reason='Cambio adicional', authorized_by='Administrador',
        ), 'superuser')
        closes.insert(CashClose(
            date=today, opening_id=first.id, cashier='Turno matutino',
            counted_cash=CUPMoney('700.00'),
        ))

        self.assertIsNone(control.get_opening(today))
        second = control.open_day(CashOpening(
            date=today, opening_amount=CUPMoney('700.00'),
            cash_limit=CUPMoney('3000.00'), opened_by='Administrador',
            shift_responsible='Turno vespertino', source_close_id=first.id,
        ), 'superuser')
        second_movement = control.add_movement(CashMovement(
            date=today, movement_type='Retiro', amount=CUPMoney('50.00'),
            reason='Retiro de seguridad', authorized_by='Administrador',
        ), 'superuser', available_cash=700.0)

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(control.get_opening(today).id, second.id)
        self.assertEqual(len(control.get_openings(today)), 2)
        self.assertEqual(len(closes.get_for_date(today)), 1)
        self.assertEqual(first_movement.opening_id, first.id)
        self.assertEqual(second_movement.opening_id, second.id)
        self.assertEqual(control.totals_for_date(today, first.id)['Entrada'], 100.0)
        self.assertEqual(control.totals_for_date(today, second.id)['Retiro'], 50.0)


if __name__ == '__main__':
    unittest.main()
