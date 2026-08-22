"""Acceso interno: administrador de tienda y vendedor."""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (QButtonGroup, QDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton,
    QStackedWidget, QVBoxLayout, QWidget)
from util.resources_path import resource_path
from view.style import tokens as t


class LoginView(QDialog):
    PROFILES = (('Administrador', 'superuser'), ('Vendedor', 'seller'))

    def __init__(self, authenticate, enter_seller, reset_password, parent=None):
        super().__init__(parent)
        self._authenticate, self._enter_seller, self._reset_password = authenticate, enter_seller, reset_password
        self.authenticated_user = None
        self.setObjectName('login_dialog'); self.setWindowTitle(f'{t.BRAND_NAME} · Acceso de tienda')
        self.setModal(True); self.setFixedSize(920, 560); self._build_ui()

    def _build_ui(self):
        page = QHBoxLayout(self); page.setContentsMargins(0, 0, 0, 0); page.setSpacing(0)
        page.addWidget(self._brand_panel(), 47); page.addWidget(self._access_panel(), 53)

    def _brand_panel(self):
        panel = QFrame(); panel.setObjectName('login_brand_panel'); layout = QVBoxLayout(panel); layout.setContentsMargins(46, 44, 40, 40)
        logo = QLabel(); logo.setPixmap(QIcon(resource_path('view/ui/images/eccos_monogram.svg')).pixmap(QSize(56, 56))); layout.addWidget(logo); layout.addSpacing(26)
        name = QLabel(t.BRAND_NAME); name.setObjectName('login_brand_name'); layout.addWidget(name)
        rule = QLabel(); rule.setObjectName('login_brand_rule'); rule.setFixedSize(52, 3); layout.addSpacing(14); layout.addWidget(rule)
        product = QLabel('PUNTO DE VENTA'); product.setObjectName('login_brand_product'); layout.addSpacing(14); layout.addWidget(product)
        tagline = QLabel('Una operación clara para el jefe de tienda y su equipo de ventas.'); tagline.setObjectName('login_brand_tagline'); tagline.setWordWrap(True); layout.addSpacing(10); layout.addWidget(tagline)
        layout.addStretch()
        for text in ('Administrador: inventario, gastos, reportes y configuración.', 'Vendedor: cotizaciones, nuevas ventas y canal comercial.', 'Los costos y márgenes permanecen sólo para administración.'):
            label = QLabel('•  ' + text); label.setObjectName('login_brand_bullet'); label.setWordWrap(True); layout.addWidget(label); layout.addSpacing(10)
        layout.addStretch(); footer = QLabel('ECCOS POS · Acceso interno de tienda'); footer.setObjectName('login_brand_footer'); layout.addWidget(footer)
        return panel

    def _access_panel(self):
        panel = QFrame(); panel.setObjectName('login_access_panel'); layout = QVBoxLayout(panel); layout.setContentsMargins(44, 42, 44, 32)
        header = QHBoxLayout(); eyebrow = QLabel('ACCESO AL SISTEMA'); eyebrow.setObjectName('section_eyebrow'); header.addWidget(eyebrow); header.addStretch()
        refresh = QPushButton('⟳  Refrescar'); refresh.setObjectName('login_link_button'); refresh.setToolTip('Reinicia el formulario de acceso'); refresh.clicked.connect(self._refresh_system); header.addWidget(refresh)
        layout.addLayout(header)
        self.title = QLabel('Selecciona tu función'); self.title.setObjectName('login_heading'); layout.addSpacing(8); layout.addWidget(self.title)
        self.help = QLabel(); self.help.setObjectName('login_help'); self.help.setWordWrap(True); layout.addSpacing(6); layout.addWidget(self.help); layout.addSpacing(18)
        self.pages = QStackedWidget(); self.pages.addWidget(self._login_page()); self.pages.addWidget(self._recovery_page()); layout.addWidget(self.pages, 1)
        self._show_login(); return panel

    def _login_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0)
        self.role_group = QButtonGroup(self); roles = QHBoxLayout(); roles.setSpacing(8)
        for index, (label, role) in enumerate(self.PROFILES):
            radio = QRadioButton(label); radio.setObjectName('login_role_radio'); radio.setProperty('role', role); radio.toggled.connect(self._refresh_role); self.role_group.addButton(radio); roles.addWidget(radio)
            if index == 0: radio.setChecked(True)
        layout.addLayout(roles); layout.addSpacing(16)
        self.username = QLineEdit(); self.username.setPlaceholderText('Usuario de administrador')
        self.password = QLineEdit(); self.password.setPlaceholderText('Contraseña'); self.password.setEchoMode(QLineEdit.Password)
        self._add_password_toggle(self.password)
        self.enter = QPushButton('Entrar como administrador'); self.enter.setObjectName('login_enter_button'); self.enter.setDefault(True); self.enter.clicked.connect(self._login)
        layout.addWidget(self.username); layout.addSpacing(9); layout.addWidget(self.password); layout.addSpacing(14); layout.addWidget(self.enter)
        self.seller_enter = QPushButton('Entrar al módulo de ventas'); self.seller_enter.setObjectName('login_enter_button'); self.seller_enter.clicked.connect(self._seller); layout.addWidget(self.seller_enter)
        forgot = QPushButton('Recuperar contraseña de administrador'); forgot.setObjectName('login_link_button'); forgot.clicked.connect(self._show_recovery); layout.addWidget(forgot); layout.addStretch()
        self._refresh_role(); return page

    def _recovery_page(self):
        page = QWidget(); form = QFormLayout(page); form.setContentsMargins(0, 0, 0, 0); form.setSpacing(10)
        self.reset_username = QLineEdit(); self.reset_username.setPlaceholderText('Administrador')
        self.reset_code = QLineEdit(); self.reset_code.setPlaceholderText('Código de recuperación'); self.reset_code.setEchoMode(QLineEdit.Password)
        self._add_password_toggle(self.reset_code)
        self.reset_password = QLineEdit(); self.reset_password.setPlaceholderText('Nueva contraseña (mínimo 8)'); self.reset_password.setEchoMode(QLineEdit.Password)
        self._add_password_toggle(self.reset_password)
        form.addRow('Usuario', self.reset_username); form.addRow('Código', self.reset_code); form.addRow('Nueva contraseña', self.reset_password)
        reset = QPushButton('Actualizar contraseña'); reset.setObjectName('login_enter_button'); reset.clicked.connect(self._recover); form.addRow('', reset)
        back = QPushButton('Volver al acceso'); back.setObjectName('login_link_button'); back.clicked.connect(self._show_login); form.addRow('', back); return page

    def _show_login(self):
        self.pages.setCurrentIndex(0); self.title.setText('Selecciona tu función'); self._refresh_role()

    def _show_recovery(self):
        self.pages.setCurrentIndex(1); self.title.setText('Recupera acceso administrativo'); self.help.setText('Usa el código de recuperación del administrador para crear una nueva contraseña.')

    def _refresh_role(self):
        if not hasattr(self, 'role_group') or self.pages.currentIndex() != 0: return
        is_seller = self.role_group.checkedButton() and self.role_group.checkedButton().property('role') == 'seller'
        self.username.setVisible(not is_seller); self.password.setVisible(not is_seller); self.enter.setVisible(not is_seller); self.seller_enter.setVisible(is_seller)
        self.help.setText('El administrador tiene control completo de la tienda.' if not is_seller else 'El vendedor puede cotizar y registrar ventas; no ve costos, ganancias ni reportes.')

    def _login(self):
        try: user = self._authenticate(self.username.text(), self.password.text(), 'superuser')
        except ValueError as error: self._error(str(error)); return
        self.authenticated_user = user; self.accept()

    def _seller(self):
        self.authenticated_user = self._enter_seller(); self.accept()

    def _recover(self):
        try: self._reset_password(self.reset_username.text(), self.reset_code.text(), self.reset_password.text())
        except ValueError as error: self._error(str(error)); return
        QMessageBox.information(self, 'Contraseña actualizada', 'La contraseña fue actualizada. Ya puedes iniciar sesión.')
        self._show_login()

    def _error(self, message): QMessageBox.warning(self, 'No se pudo continuar', message)

    def _refresh_system(self):
        """Reinicia el formulario de acceso a su estado inicial."""
        self.username.clear(); self.password.clear()
        self.reset_username.clear(); self.reset_code.clear(); self.reset_password.clear()
        self.role_group.buttons()[0].setChecked(True)
        self._show_login()

    @staticmethod
    def _eye_icon(visible):
        """Genera el icono del ojito a partir de un emoji, sin depender de assets externos."""
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setFont(QFont('Segoe UI Emoji', 12))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, '🙈' if visible else '👁')
        painter.end()
        return QIcon(pixmap)

    def _add_password_toggle(self, line_edit: QLineEdit):
        """Agrega el icono de ojito para mostrar/ocultar la contraseña al escribirla."""
        action = line_edit.addAction(self._eye_icon(False), QLineEdit.TrailingPosition)
        action.setToolTip('Mostrar contraseña')

        def toggle_visibility():
            visible = line_edit.echoMode() == QLineEdit.Normal
            line_edit.setEchoMode(QLineEdit.Password if visible else QLineEdit.Normal)
            action.setIcon(self._eye_icon(not visible))
            action.setToolTip('Mostrar contraseña' if visible else 'Ocultar contraseña')

        action.triggered.connect(toggle_visibility)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape: event.ignore()
        else: super().keyPressEvent(event)
