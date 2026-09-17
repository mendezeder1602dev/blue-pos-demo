import unittest
from datetime import datetime, timedelta

from model.cash_shift_status import cash_shift_status, find_unclosed_opening


class CashShiftStatusTest(unittest.TestCase):
    def test_reports_elapsed_hours_and_warning_after_eight_hours(self):
        now = datetime(2026, 9, 17, 18, 30)

        status = cash_shift_status(now - timedelta(hours=9, minutes=15), now, now.date())

        self.assertEqual(status.elapsed_label, '9 h 15 min')
        self.assertEqual(status.level, 'warning')

    def test_previous_day_is_overdue_even_when_elapsed_time_is_short(self):
        now = datetime(2026, 9, 17, 0, 30)

        status = cash_shift_status(
            now - timedelta(hours=1), now, (now - timedelta(days=1)).date())

        self.assertEqual(status.level, 'overdue')
        self.assertTrue(status.crossed_day)

    def test_falls_back_when_hot_reloaded_repository_lacks_the_new_method(self):
        open_shift = type('Opening', (), {
            'id': 1, 'date': datetime(2026, 9, 16).date(),
            'created_at': datetime(2026, 9, 16, 9, 0),
        })()
        closed_shift = type('Opening', (), {
            'id': 2, 'date': datetime(2026, 9, 15).date(),
            'created_at': datetime(2026, 9, 15, 9, 0),
        })()
        legacy_control = type('LegacyControl', (), {
            'get_all_openings': lambda self, register_id: [closed_shift, open_shift],
        })()
        close_repository = type('Closes', (), {
            'get_all': lambda self: [type('Close', (), {'opening_id': 2})()],
        })()

        result = find_unclosed_opening(legacy_control, close_repository, register_id=10)

        self.assertEqual(result.id, 1)
