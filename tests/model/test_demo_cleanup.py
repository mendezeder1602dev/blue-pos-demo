import unittest

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from model.entity.models import Base, BusinessProfile, Expense, Product, Sale
from model.schema import DEMO_CLEANUP_MIGRATION, _clean_demo_operational_data_once
from model.util.monetary_types import CUPMoney


class DemoCleanupTest(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:', future=True)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            product = Product(
                name='Artículo de prueba', description='Solo para depuración',
                price=CUPMoney('40.00'), cost=CUPMoney('20.00'), quantity=3)
            session.add(product)
            session.flush()
            session.add(Sale(
                product_id=product.id, price=CUPMoney('40.00'), cost=CUPMoney('20.00')))
            session.add(Expense(
                name='Gasto de prueba', description='', spent_money=CUPMoney('10.00')))
            session.add(BusinessProfile(business_name='Grupo ECCOS'))
            session.commit()

    def test_cleanup_removes_operations_and_preserves_business_profile(self):
        self.assertTrue(_clean_demo_operational_data_once(self.engine))

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Product.id))), 0)
            self.assertEqual(session.scalar(select(func.count(Sale.id))), 0)
            self.assertEqual(session.scalar(select(func.count(Expense.id))), 0)
            self.assertEqual(session.scalar(select(func.count(BusinessProfile.id))), 1)

    def test_cleanup_is_applied_only_once(self):
        self.assertTrue(_clean_demo_operational_data_once(self.engine))
        with Session(self.engine) as session:
            session.add(Product(
                name='Producto posterior', description='No debe borrarse',
                price=CUPMoney('15.00'), cost=CUPMoney('5.00'), quantity=1))
            session.commit()

        self.assertFalse(_clean_demo_operational_data_once(self.engine))

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Product.id))), 1)
            marker = session.execute(
                text('SELECT COUNT(*) FROM deployment_migrations WHERE migration_key = :key'),
                {'key': DEMO_CLEANUP_MIGRATION}).scalar_one()
            self.assertEqual(marker, 1)


if __name__ == '__main__':
    unittest.main()
