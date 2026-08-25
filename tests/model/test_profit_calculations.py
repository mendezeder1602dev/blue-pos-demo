import unittest
from types import SimpleNamespace

from model import economy
from model.util.monetary_types import CUPMoney


class ProfitCalculationsTest(unittest.TestCase):
    def test_sales_cost_and_profit_are_distinct(self):
        sale = SimpleNamespace(
            price=CUPMoney('40.00'), cost=CUPMoney('20.00'),
            profit=CUPMoney('20.00'))

        gross_sales = economy.calculate_collected_money([sale])
        gross_profit = economy.calculate_total_profit([sale])
        cost_of_goods = gross_sales - gross_profit
        net_profit = gross_profit - CUPMoney('5.00')

        self.assertEqual(float(gross_sales.amount), 40.0)
        self.assertEqual(float(cost_of_goods.amount), 20.0)
        self.assertEqual(float(gross_profit.amount), 20.0)
        self.assertEqual(float(net_profit.amount), 15.0)


if __name__ == '__main__':
    unittest.main()
