import unittest
from datetime import datetime

from model.timezone import MEXICO_CENTRAL_TIMEZONE, mexico_now, mexico_today


class TestMexicoTimezone(unittest.TestCase):
    def test_operational_clock_uses_mexico_city_calendar(self):
        expected = datetime.now(MEXICO_CENTRAL_TIMEZONE)
        actual = mexico_now()

        self.assertIsNone(actual.tzinfo)
        self.assertLess(abs((actual - expected.replace(tzinfo=None)).total_seconds()), 2)
        self.assertEqual(mexico_today(), expected.date())


if __name__ == '__main__':
    unittest.main()
