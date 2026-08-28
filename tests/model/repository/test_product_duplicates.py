import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.entity.models import Base, Product
from model.repository.exc.product import UniqueProductBarcodeException, UniqueProductNameException
from model.repository.product import ProductRepository
from model.util.monetary_types import CUPMoney


def product(name, barcode=''):
    return Product(name=name, description='Producto de prueba',
                   price=CUPMoney('20.00'), cost=CUPMoney('10.00'),
                   quantity=1, barcode=barcode)


class TestProductDuplicates(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.repository = ProductRepository(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_name_comparison_ignores_case_and_repeated_spaces(self):
        self.repository.insert_product(product('Coca Cola', '75010001'))
        with self.assertRaises(UniqueProductNameException):
            self.repository.insert_product(product('  COCA   cola  ', '75010002'))

    def test_barcode_alert_identifies_existing_product(self):
        self.repository.insert_product(product('Producto original', '75010003'))
        with self.assertRaisesRegex(UniqueProductBarcodeException, 'Producto original'):
            self.repository.insert_product(product('Producto nuevo', '75010003'))


if __name__ == '__main__':
    unittest.main()
