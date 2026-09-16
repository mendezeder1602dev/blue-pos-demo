import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class TestWebAppSmoke(unittest.TestCase):
    def test_credit_checkout_requires_confirmed_complete_customer_profile(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')

        self.assertIn("@st.dialog('Confirma los datos del cliente'", source)
        self.assertIn("'Domicilio *'", source)
        self.assertIn("'Confirmar y continuar'", source)
        self.assertIn("_credit_customer_confirmed_id", source)
        self.assertNotIn("'Confirmo que los datos están actualizados'", source)
        self.assertIn("'customer_id': credit_data.get('customer_id')", source)

    def test_seller_navigation_includes_customer_directory(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')
        source_tree = ast.parse(source)
        seller_pages = next(
            node for node in source_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'SELLER_PAGES'
                    for target in node.targets))

        page_names = {
            key.value for key in seller_pages.value.keys
            if isinstance(key, ast.Constant)
        }
        self.assertIn('Clientes', page_names)

    def test_admin_primary_navigation_exposes_customer_directory(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')
        source_tree = ast.parse(source)
        navigation = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == '_render_sidebar_navigation')
        navigation_source = ast.get_source_segment(source, navigation)

        daily_start = navigation_source.index("('Operación diaria', (")
        cash_start = navigation_source.index("('Caja', (", daily_start)
        daily_navigation = navigation_source[daily_start:cash_start]
        self.assertIn("('Clientes', 'Clientes', ':material/groups:')", daily_navigation)

    def test_sidebar_promotes_settings_and_left_aligns_every_action(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')
        source_tree = ast.parse(source)
        render_app = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef) and node.name == '_render_app')
        render_app_source = ast.get_source_segment(source, render_app)
        navigation = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == '_render_sidebar_navigation')
        navigation_source = ast.get_source_segment(source, navigation)

        self.assertIn("'Configuración del sistema'", render_app_source)
        self.assertIn("key='sidebar_utility_settings'", render_app_source)
        self.assertNotIn(
            "('Configuración', 'Configuración', ':material/settings:')",
            navigation_source)
        self.assertIn(
            '[data-testid="stSidebar"] .stButton > button', source)
        self.assertIn('justify-content:flex-start !important', source)
        self.assertIn(
            '[data-testid="stSidebar"] .st-key-sidebar_utility_settings', source)
        self.assertIn('color:#F8FAFC !important', source)

    def test_customer_create_and_edit_use_focused_dialogs(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')

        self.assertIn("@st.dialog('Registrar cliente'", source)
        self.assertIn("@st.dialog('Editar cliente'", source)
        self.assertIn("'Nuevo cliente', type='primary'", source)
        self.assertIn("selection_mode='single-row'", source)
        self.assertIn("_customer_edit_dialog(selected_customer.id)", source)
        self.assertNotIn("st.markdown('#### Editar cliente')", source)
        self.assertIn("'País y lada *'", source)
        self.assertIn("'Código postal'", source)
        self.assertIn("phone_country=phone_country", source)
        self.assertIn("postal_code=postal_code", source)

    def test_inventory_summary_is_compact_and_money_based(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')
        source_tree = ast.parse(source)
        summary = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == '_render_inventory_financial_summary')
        summary_source = ast.get_source_segment(source, summary)

        self.assertIn("'Valor a precio cliente'", summary_source)
        self.assertIn("'Dinero invertido'", summary_source)
        self.assertIn("'Ganancia potencial'", summary_source)
        self.assertIn("st.bar_chart(chart_frame, horizontal=True, height=210)", summary_source)
        self.assertNotIn("'Estadística por categoría'", summary_source)

    def test_credit_portfolio_uses_selectable_table_and_focused_dialogs(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')

        self.assertIn("@st.dialog('Nueva cuenta'", source)
        self.assertIn("@st.dialog('Registrar abono'", source)
        self.assertIn("@st.dialog('Detalle de la cuenta'", source)
        self.assertIn("key='credit_portfolio_table'", source)
        self.assertIn("selection_mode='single-row'", source)
        self.assertIn("'Vencidas'", source)
        self.assertNotIn("with st.expander('Registrar cuenta'", source)

    def test_seven_day_pulse_lives_in_statistics_not_dashboard(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')
        source_tree = ast.parse(source)
        dashboard = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef) and node.name == '_render_dashboard')
        statistics = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef) and node.name == '_render_statistics')
        dashboard_source = ast.get_source_segment(source, dashboard)
        statistics_source = ast.get_source_segment(source, statistics)

        self.assertIn('def _render_statistics_weekly_pulse', source)
        self.assertIn("timedelta(days=6)", source)
        self.assertIn("'Pulso de los últimos 7 días'", source)
        self.assertNotIn('_render_statistics_weekly_pulse', dashboard_source)
        self.assertIn('_render_statistics_weekly_pulse(today)', statistics_source)

    def test_dashboard_does_not_include_pos_activation_progress(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')

        self.assertNotIn("def _render_pos_activation", source)
        self.assertNotIn("'Activa tu POS'", source)

    def test_dashboard_restores_operational_layout_without_compact_experiment(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')
        source_tree = ast.parse(source)
        dashboard = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef) and node.name == '_render_dashboard')
        dashboard_source = ast.get_source_segment(source, dashboard)

        self.assertIn("'Centro de operación'", dashboard_source)
        self.assertIn("'Caja rápida'", dashboard_source)
        self.assertIn("'Herramientas de venta'", dashboard_source)
        self.assertNotIn("'Tu negocio hoy'", dashboard_source)
        self.assertNotIn("'_dashboard_alert_signature'", dashboard_source)
        self.assertNotIn('st.toast(', dashboard_source)

    def test_navigation_does_not_mutate_an_instantiated_command_center_widget(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source_tree = ast.parse(app_path.read_text(encoding='utf-8'))
        navigation = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef) and node.name == '_navigate_to_page')
        navigation_source = ast.get_source_segment(
            app_path.read_text(encoding='utf-8'), navigation)

        self.assertNotIn("['command_center_page_jump'] =", navigation_source)

    def test_product_editor_uses_a_modal_dialog(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')

        self.assertIn("@st.dialog('Editar producto'", source)
        self.assertIn("'Abrir editor'", source)

    def test_product_creation_uses_a_modal_dialog(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')

        self.assertIn("@st.dialog('Agregar producto'", source)
        self.assertIn("'Nuevo producto'", source)

    def test_long_action_lists_use_bounded_scrollable_mosaics(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')
        source_tree = ast.parse(source)

        for function_name in (
                '_render_quotes', '_render_cash_close', '_render_multicash_dashboard'):
            function = next(
                node for node in ast.walk(source_tree)
                if isinstance(node, ast.FunctionDef) and node.name == function_name)
            function_source = ast.get_source_segment(source, function)
            self.assertIn('st.container(height=', function_source)
            self.assertIn('for row_start in range(0,', function_source)

    def test_admin_login_dashboard_and_new_pages_render(self):
        with tempfile.TemporaryDirectory() as folder:
            environment = {
                'BLUE_POS_DATABASE_URL': (
                    f"sqlite:///{Path(folder) / 'data.db'}?check_same_thread=False"),
                'BLUE_POS_AUTH_DATABASE_URL': (
                    f"sqlite:///{Path(folder) / 'auth.db'}?check_same_thread=False"),
                'BLUE_POS_ADMIN_USER': 'admin_smoke',
                'BLUE_POS_ADMIN_PASSWORD': 'SmokePassword2026',
                'BLUE_POS_RECOVERY_CODE': 'SMOKE2026',
            }
            with patch.dict(os.environ, environment, clear=False):
                app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
                app = AppTest.from_file(str(app_path), default_timeout=20).run()
                self.assertFalse(app.exception)
                login_user = next(widget for widget in app.text_input
                                  if widget.label == 'Usuario')
                login_password = next(widget for widget in app.text_input
                                      if widget.label == 'Contraseña')
                login_user.set_value('admin_smoke')
                login_password.set_value('SmokePassword2026')
                next(button for button in app.button
                     if button.label == 'Iniciar sesión').click()
                app.run()
                self.assertFalse(app.exception)
                for page in ('Centro de incidencias', 'Créditos y cartera',
                             'Vendedores', 'Clientes', 'Abastecimiento', 'Salud operativa',
                             'Configuración', 'Métodos de pago', 'Mi perfil', 'Inventario'):
                    app.session_state['page'] = page
                    app.run()
                    self.assertFalse(app.exception, page)

    def test_command_center_page_picker_uses_session_state_as_its_only_default(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source_tree = ast.parse(app_path.read_text(encoding='utf-8'))
        picker = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'selectbox'
            and any(
                isinstance(argument, ast.Constant)
                and argument.value == 'Buscar módulo del sistema'
                for argument in node.args))

        self.assertFalse(any(keyword.arg == 'index' for keyword in picker.keywords))

    def test_quick_actions_render_as_a_dashboard_only_mosaic(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')
        source_tree = ast.parse(source)
        command_center = next(
            node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == '_render_command_center')
        command_center_source = ast.get_source_segment(source, command_center)

        self.assertIn("if current_page == 'Tablero':", command_center_source)
        self.assertIn("st.columns(3, gap='small')", command_center_source)
        self.assertIn('action_columns[index % len(action_columns)]',
                      command_center_source)

    def test_dashboard_indicator_copy_is_bolder_and_numeric_values_align_right(self):
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')

        self.assertIn("value_kind = ('number' if any(", source)
        self.assertIn("key=f'dashboard-kpi-{value_kind}-{key}'", source)
        self.assertIn(
            '[class*="st-key-dashboard-kpi-"] [data-testid="stCaptionContainer"]',
            source)
        self.assertIn('font-size:.84rem; font-weight:650;', source)
        self.assertIn(
            '[class*="st-key-dashboard-kpi-number-"] [data-testid="stMetricValue"]',
            source)
        self.assertIn('text-align:right;', source)

    def test_customer_views_tolerate_streamlit_with_a_stale_customer_model(self):
        """A hot reload must not crash while the process still has the old ORM class."""
        app_path = Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        source = app_path.read_text(encoding='utf-8')

        self.assertNotIn('customer.address', source)
        self.assertIn("getattr(customer, 'address', '')", source)
