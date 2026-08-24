import json
import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.entity.models import Base, CashClose, CashOpening
from model.repository.cash_close import CashCloseRepository
from model.repository.cash_control import CashControlRepository
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
        previous_date = date.today() - timedelta(days=1)
        previous_close = close_repository.insert(CashClose(
            date=previous_date, cashier='Administrador',
            counted_cash=CUPMoney('1250.00'),
            denomination_details=json.dumps({'bill_500': 2, 'bill_200': 1, 'bill_50': 1}),
        ))

        latest = close_repository.get_latest_before(date.today())
        self.assertEqual(latest.id, previous_close.id)
        self.assertEqual(float(latest.counted_cash.amount), 1250.0)

        opening = CashControlRepository(self.session).open_day(CashOpening(
            date=date.today(), opening_amount=latest.counted_cash,
            cash_limit=CUPMoney('3000.00'), opened_by='Administrador',
            denomination_details=latest.denomination_details,
            source_close_id=latest.id,
        ), 'superuser')
        self.assertEqual(opening.source_close_id, previous_close.id)
        self.assertEqual(float(opening.opening_amount.amount), 1250.0)

    def test_seller_cannot_confirm_opening(self):
        with self.assertRaises(PermissionError):
            CashControlRepository(self.session).open_day(CashOpening(
                date=date.today(), opening_amount=CUPMoney('500.00'),
                cash_limit=CUPMoney('3000.00'), opened_by='Vendedor',
            ), 'store')


if __name__ == '__main__':
    unittest.main()
