"""Estado temporal de los turnos de caja abiertos."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CashShiftStatus:
    elapsed_minutes: int
    elapsed_label: str
    level: str
    crossed_day: bool


@dataclass(frozen=True)
class CashFleetSummary:
    open_count: int
    overdue_count: int
    oldest_label: str | None


def cash_shift_status(opened_at, now, opening_date, warning_hours=8):
    """Calcula duración y severidad sin modificar ni cerrar el turno."""
    elapsed_minutes = max(0, int((now - opened_at).total_seconds() // 60))
    hours, minutes = divmod(elapsed_minutes, 60)
    crossed_day = opening_date < now.date()
    level = ('overdue' if crossed_day else
             'warning' if elapsed_minutes >= int(warning_hours * 60) else 'normal')
    return CashShiftStatus(
        elapsed_minutes=elapsed_minutes,
        elapsed_label=f'{hours} h {minutes:02d} min',
        level=level,
        crossed_day=crossed_day,
    )


def summarize_cash_fleet(openings, now):
    """Resume pendientes de todas las cajas para decisiones administrativas."""
    pending = list(openings)
    if not pending:
        return CashFleetSummary(0, 0, None)
    statuses = [
        cash_shift_status(opening.created_at, now, opening.date)
        for opening in pending
    ]
    oldest = max(statuses, key=lambda status: status.elapsed_minutes)
    return CashFleetSummary(
        open_count=len(pending),
        overdue_count=sum(status.level == 'overdue' for status in statuses),
        oldest_label=oldest.elapsed_label,
    )


def find_unclosed_opening(control_repository, close_repository, register_id):
    """Obtiene el turno pendiente y tolera repositorios previos a una recarga."""
    current_method = getattr(control_repository, 'get_unclosed_opening', None)
    if callable(current_method):
        return current_method(register_id)

    closed_ids = {
        close.opening_id for close in close_repository.get_all()
        if getattr(close, 'opening_id', None) is not None
    }
    pending = [
        opening for opening in control_repository.get_all_openings(register_id)
        if opening.id not in closed_ids
    ]
    return min(
        pending,
        key=lambda opening: (opening.date, opening.created_at, opening.id),
        default=None,
    )
