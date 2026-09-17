from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from model.cash_shift_status import summarize_cash_fleet


@pytest.mark.unit
@pytest.mark.parametrize(
    ('ages', 'dates', 'expected_open', 'expected_overdue', 'expected_oldest'),
    [
        ([], [], 0, 0, None),
        ([2], [date(2026, 9, 17)], 1, 0, '2 h 00 min'),
        ([3, 27], [date(2026, 9, 17), date(2026, 9, 16)], 2, 1, '27 h 00 min'),
    ],
    ids=('sin-turnos', 'turno-actual', 'incluye-turno-vencido'),
)
def test_summarize_cash_fleet_prioritizes_unclosed_and_overdue_shifts(
        ages, dates, expected_open, expected_overdue, expected_oldest):
    now = datetime(2026, 9, 17, 12, 0)
    openings = [
        SimpleNamespace(id=index + 1, created_at=now - timedelta(hours=age),
                        date=opening_date, register_id=index + 10)
        for index, (age, opening_date) in enumerate(zip(ages, dates))
    ]

    summary = summarize_cash_fleet(openings, now)

    assert summary.open_count == expected_open
    assert summary.overdue_count == expected_overdue
    assert summary.oldest_label == expected_oldest
