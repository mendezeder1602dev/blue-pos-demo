import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class TestWebAppSmoke(unittest.TestCase):
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
                             'Vendedores', 'Abastecimiento'):
                    app.session_state['page'] = page
                    app.run()
                    self.assertFalse(app.exception, page)
