from datetime import date
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.entity.models import Base, Expense, Product, Sale
from model.repository.economic_summary import EconomicSummaryRepository
from model.util.monetary_types import CUPMoney


class TestEconomicSummaryTrend(unittest.TestCase):
    """Pruebas aisladas para los datos que alimentan el pulso del tablero."""

    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.repository = EconomicSummaryRepository(self.session)
        self.product = Product(
            name='Producto de tendencia', price=CUPMoney('100.00'),
            cost=CUPMoney('40.00'), quantity=10)
        self.session.add(self.product)
        self.session.flush()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_daily_trend_groups_tickets_and_excludes_cancelled_sales(self):
        first_day = date(2026, 9, 10)
        second_day = date(2026, 9, 11)
        self.session.add_all((
            Sale(product_id=self.product.id, date=first_day, price=CUPMoney('100.00'),
                 cost=CUPMoney('40.00'), transaction_id='ticket-1', status='Completada'),
            Sale(product_id=self.product.id, date=first_day, price=CUPMoney('50.00'),
                 cost=CUPMoney('20.00'), transaction_id='ticket-1', status='Completada'),
            Sale(product_id=self.product.id, date=first_day, price=CUPMoney('99.00'),
                 cost=CUPMoney('10.00'), transaction_id='cancelled', status='Anulada'),
            Sale(product_id=self.product.id, date=second_day, price=CUPMoney('80.00'),
                 cost=CUPMoney('30.00'), transaction_id=None, status='Completada'),
            Expense(name='Gasto de tendencia', date=first_day,
                    spent_money=CUPMoney('15.00'), is_active=True),
        ))
        self.session.commit()

        trend = self.repository.get_daily_trend(first_day, second_day)

        self.assertEqual(
            trend[first_day],
            {'sales': 150.0, 'cost': 60.0, 'units': 2, 'tickets': 1, 'expenses': 15.0})
        self.assertEqual(
            trend[second_day],
            {'sales': 80.0, 'cost': 30.0, 'units': 1, 'tickets': 1, 'expenses': 0.0})


if __name__ == '__main__':
    unittest.main()
