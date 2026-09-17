import unittest
from types import SimpleNamespace

from model.sales_pricing import sale_unit_price
from model.util.monetary_types import CUPMoney


class SalesPricingTest(unittest.TestCase):
    def setUp(self):
        self.product = SimpleNamespace(
            price=CUPMoney('100.00'),
            wholesale_min_quantity=10,
            wholesale_price=CUPMoney('75.00'),
        )

    def test_quantity_never_applies_the_wholesale_price_automatically(self):
        self.assertEqual(sale_unit_price(self.product, quantity=100), 100.00)

    def test_explicit_and_restored_prices_are_preserved(self):
        self.assertEqual(
            sale_unit_price(self.product, quantity=100, configured_price=92.50),
            92.50,
        )
        self.assertEqual(
            sale_unit_price(
                self.product, quantity=100, configured_price=92.50,
                locked_price=80.00,
            ),
            80.00,
        )
