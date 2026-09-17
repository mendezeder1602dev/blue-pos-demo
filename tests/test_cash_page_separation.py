import ast
import unittest
from pathlib import Path


class TestCashPageSeparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        ).read_text(encoding='utf-8')
        source_tree = ast.parse(cls.source)
        cls.functions = {
            node.name: ast.get_source_segment(cls.source, node)
            for node in source_tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_cash_close_only_handles_the_current_cut(self):
        cash_close = self.functions['_render_cash_close']

        self.assertNotIn('Historial de cortes', cash_close)
        self.assertNotIn('repository.get_all()', cash_close)
        self.assertNotIn('cash_close_history_grid', cash_close)
        self.assertNotIn("'Abrir caja'", cash_close)
        self.assertNotIn('CashOpening(', cash_close)

    def test_cash_opening_does_not_render_a_shift_history(self):
        cash_opening = self.functions['_render_cash_opening']

        self.assertNotIn('Historial de turnos', cash_opening)
        self.assertNotIn('get_all_openings(', cash_opening)
        self.assertNotIn('cash_history_status_filter', cash_opening)

    def test_history_page_owns_previous_shifts_cuts_and_exports(self):
        cash_history = self.functions['_render_cash_history']

        self.assertIn('get_all_openings(', cash_history)
        self.assertIn('close_repository.get_all()', cash_history)
        self.assertIn("'Estado del turno'", cash_history)
        self.assertIn('Corte asociado', cash_history)
        self.assertIn("'Descargar PDF del corte'", cash_history)
        self.assertIn("'Descargar Excel del corte'", cash_history)

    def test_dashboard_cash_health_handles_closed_or_overdue_registers(self):
        dashboard = self.functions['_render_dashboard']

        initialization = dashboard.index('estimated_cash = 0.0')
        health_check = dashboard.index('cash_over_limit =')
        self.assertLess(initialization, health_check)
        normalized_dashboard = ' '.join(dashboard.split())
        self.assertIn(
            'bool( opening and not stale_opening and estimated_cash > limit)',
            normalized_dashboard,
        )

    def test_cash_close_automatically_targets_the_pending_shift(self):
        navigation = self.functions['_navigate_to_cash_close']
        cash_close = self.functions['_render_cash_close']

        self.assertNotIn('session_state', navigation)
        self.assertIn('_get_unclosed_opening(active_register.id)', cash_close)
        self.assertIn('selected_date = opening.date if opening else mexico_today()', cash_close)
        self.assertNotIn("st.date_input('Fecha del corte'", cash_close)

    def test_pending_shift_always_exposes_the_close_action(self):
        cash_close = self.functions['_render_cash_close']

        self.assertNotIn('selected_date == mexico_today()', cash_close)
        self.assertIn('Turno pendiente #', cash_close)
        self.assertIn('cash_shift_status(', cash_close)
        self.assertIn("'Realizar corte y cerrar caja'", cash_close)

    def test_dashboard_exposes_actionable_cash_fleet_control(self):
        dashboard = self.functions['_render_dashboard']

        self.assertIn("'Control de cajas'", dashboard)
        self.assertIn("'Turnos sin cerrar'", dashboard)
        self.assertIn("'Vencidos'", dashboard)
        self.assertIn("'Realizar corte de la caja seleccionada'", dashboard)
        self.assertIn('_select_cash_register_and_close', dashboard)

    def test_dashboard_summary_survives_a_stale_hot_reloaded_module(self):
        self.assertNotIn(
            'cash_shift_status, find_unclosed_opening, summarize_cash_fleet,',
            self.source,
        )
        self.assertIn('def _summarize_cash_fleet_compat(openings, now):', self.source)


if __name__ == '__main__':
    unittest.main()
