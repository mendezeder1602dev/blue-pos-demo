from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import QSize, QPropertyAnimation, QPoint, QSequentialAnimationGroup, pyqtSignal
from PyQt5.QtGui import QMouseEvent, QPaintEvent, QPixmap
from PyQt5.QtWidgets import (
    QFrame, QApplication, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QToolButton, QVBoxLayout, QWidget,
)
from PyQt5.uic import loadUi
from view.util.animations import GoForwardAndReturnAnimation
from util.resources_path import resource_path
from view.style.blue import BLUE_STYLE

NEW_SALE_LABEL = 'Nueva venta'
EXPRESS_SALE_LABEL = 'Venta rápida'
SALES_CHANNEL_LABEL = 'Canal de ventas'
ZERO_MXN = '0.00 MXN'
REPORT_ICON = 'eccos_report.svg'


class MainView(QFrame):

    clicked_on_next_frame = pyqtSignal()
    clicked_on_previous_frame = pyqtSignal()
    clicked_on_about_label = pyqtSignal()

    def __init__(self, presenter, active_user=None):
        super().__init__()
        self.__presenter = presenter
        self.__next_frame_animation = None
        self.__previous_frame_animation = None
        self.__active_user = active_user

        self.__set_up_gui()
        self.__pages_of_stacked_widget = [
            self.dashboard_widget,
            self.statistics_widget,
            self.management_widget,
            self.reports_widget
        ]
        self.__selected_page_index = 0
        self.stacked_widget.setCurrentWidget(self.dashboard_widget)

    def __set_up_gui(self):
        loadUi(resource_path('view/ui/main.ui'), self)
        self.wire_up_gui_connections()
        self.__apply_control_center_layout()

    def __apply_control_center_layout(self):
        """Convierte el inicio en una navegación visual tipo plataforma de video."""
        self.__business = self.__presenter.get_business_profile_data()
        self.__create_side_navigation()
        self.frame_11.hide()
        self.__apply_formal_iconography()
        self.dashboard_widget = self.__create_pos_dashboard()
        self.stacked_widget.addWidget(self.dashboard_widget)
        # Al reemplazar la portada original, seleccionar de inmediato el
        # tablero del perfil evita que Qt conserve una página vacía previa.
        self.stacked_widget.setCurrentWidget(self.dashboard_widget)
        for page in (self.management_widget, self.reports_widget, self.statistics_widget):
            page.layout().setContentsMargins(24, 18, 24, 24)

    def __create_side_navigation(self):
        self.frame_12.show()
        self.frame_12.setObjectName('side_navigation')
        self.frame_12.setFixedWidth(210)
        container_layout = self.frame_12.layout()
        while container_layout.count():
            item = container_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
        container_layout.setContentsMargins(10, 14, 10, 14)
        sidebar = QFrame()
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(4, 2, 4, 2)
        self.__business_logo_label = QLabel()
        self.__business_logo_label.setObjectName('side_business_logo')
        self.__business_logo_label.setFixedSize(44, 44)
        self.__business_logo_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.__business_logo_label)
        self.__business_brand_label = QLabel(); self.__business_brand_label.setObjectName('side_brand'); layout.addWidget(self.__business_brand_label)
        self.__business_caption_label = QLabel(); self.__business_caption_label.setObjectName('side_caption'); layout.addWidget(self.__business_caption_label)
        self.__refresh_business_brand()
        refresh_button = QToolButton(); refresh_button.setObjectName('side_nav_button'); refresh_button.setText('⟳  Refrescar'); refresh_button.setToolTip('Actualiza los datos del tablero')
        refresh_button.clicked.connect(self.refresh_dashboard); layout.addWidget(refresh_button)
        layout.addSpacing(6)
        if self.__presenter.is_administrator():
            entries = (
                ('Inicio', lambda: self.__show_page(0)), (NEW_SALE_LABEL, self.__presenter.open_sales_terminal),
                (EXPRESS_SALE_LABEL, self.__presenter.open_express_sale), ('Inventario', self.__presenter.open_product_management),
                ('Cotizaciones', self.__presenter.open_quote), (SALES_CHANNEL_LABEL, self.__presenter.open_sales_channel),
                ('Reportes', lambda: self.__show_page(3)), ('Análisis', lambda: self.__show_page(1)),
            )
        else:
            entries = (
                (NEW_SALE_LABEL, self.__presenter.open_sales_terminal), (EXPRESS_SALE_LABEL, self.__presenter.open_express_sale),
                ('Cotizaciones', self.__presenter.open_quote), (SALES_CHANNEL_LABEL, self.__presenter.open_sales_channel),
            )
        for title, handler in entries:
            button = QToolButton(); button.setObjectName('side_nav_button'); button.setText(title)
            button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly); button.clicked.connect(handler); layout.addWidget(button)
        layout.addStretch()
        if self.__presenter.is_administrator():
            profile = QToolButton(); profile.setObjectName('side_nav_button'); profile.setText('Mi negocio'); profile.clicked.connect(self.__presenter.open_business_profile); layout.addWidget(profile)
        logout = QToolButton(); logout.setObjectName('side_nav_button'); logout.setText('Cerrar sesión'); logout.clicked.connect(self.__presenter.logout); layout.addWidget(logout)
        layout.addWidget(QLabel('Sucursal principal · Sesión local', objectName='side_caption'))
        container_layout.addWidget(sidebar)

    def apply_business_profile(self, business: dict):
        """Actualiza la identidad visible inmediatamente después de guardar el perfil."""
        self.__business = business
        self.__refresh_business_brand()

    def refresh_dashboard(self):
        """Reconstruye el tablero de inicio con los datos más recientes sin perder la página activa."""
        current_page = self.__selected_page_index
        self.__business = self.__presenter.get_business_profile_data()
        self.__refresh_business_brand()
        new_dashboard = self.__create_pos_dashboard()
        old_dashboard = self.dashboard_widget
        index = self.stacked_widget.indexOf(old_dashboard)
        self.stacked_widget.removeWidget(old_dashboard)
        old_dashboard.deleteLater()
        self.dashboard_widget = new_dashboard
        self.stacked_widget.insertWidget(index, new_dashboard)
        self.__pages_of_stacked_widget[0] = new_dashboard
        self.stacked_widget.setCurrentWidget(self.__pages_of_stacked_widget[current_page])

    def __refresh_business_brand(self):
        name = self.__business.get('business_name') or 'Mi negocio'
        owner = self.__business.get('owner_name') or 'Punto de venta'
        self.__business_brand_label.setText(f'●  {name}')
        self.__business_caption_label.setText(owner.upper())
        logo_path = self.__business.get('logo_path')
        logo = QPixmap(logo_path) if logo_path else QPixmap()
        if not logo.isNull():
            self.__business_logo_label.setPixmap(logo.scaled(
                40, 40, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            self.__business_logo_label.setText('')
        else:
            self.__business_logo_label.setPixmap(QPixmap())
            self.__business_logo_label.setText(name[:1].upper())
        profile = self.__active_user.role if self.__active_user else 'client'
        self.setWindowTitle(f'{name} · {profile.title()}')

    def __create_pos_dashboard(self):
        if not self.__presenter.is_administrator():
            return self.__create_seller_dashboard()
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(16)
        heading = QLabel('Operación de caja')
        heading.setObjectName('dashboard_title')
        layout.addWidget(heading)
        subtitle = QLabel('Turno activo · Caja principal · Controla ventas, inventario y resultados en un solo lugar')
        subtitle.setObjectName('dashboard_subtitle')
        layout.addWidget(subtitle)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)
        summary = self.__get_dashboard_summary()
        for index, (caption, key) in enumerate((
                ('Ventas de hoy', 'sales'), ('Operaciones', 'operations'),
                ('Gastos de hoy', 'expenses'), ('Utilidad neta', 'net_profit'))):
            metrics.addWidget(self.__create_metric_card(caption, summary[key]), 0, index)
        layout.addLayout(metrics)

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self.__create_sales_card(), 3)
        content.addWidget(self.__create_quick_access_card(summary['products']), 2)
        layout.addLayout(content)
        layout.addWidget(self.__create_low_stock_card())
        layout.addStretch()
        return dashboard

    def __create_low_stock_card(self):
        low_stock_products = self.__get_low_stock_products()
        card = QFrame()
        card.setObjectName('pos_card')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        title = QLabel('Alerta de inventario')
        title.setObjectName('pos_card_title')
        layout.addWidget(title)
        if not low_stock_products:
            message = QLabel(f'Todos los productos tienen más de {self.__presenter.LOW_STOCK_THRESHOLD} unidades disponibles.')
            message.setObjectName('dashboard_subtitle')
            message.setWordWrap(True)
            layout.addWidget(message)
        else:
            description = QLabel('Estos productos están por agotarse, considera reabastecerlos pronto:')
            description.setObjectName('dashboard_subtitle')
            description.setWordWrap(True)
            layout.addWidget(description)
            for product in low_stock_products:
                row = QLabel(f"•  {product['name']} — {product['quantity']} unidades")
                row.setObjectName('dashboard_subtitle')
                layout.addWidget(row)
        return card

    def __get_low_stock_products(self):
        if hasattr(self.__presenter, 'get_low_stock_products'):
            return self.__presenter.get_low_stock_products()
        return []

    def __create_seller_dashboard(self):
        """El vendedor sólo ve las herramientas necesarias para atender."""
        dashboard = QWidget(); layout = QVBoxLayout(dashboard); layout.setContentsMargins(24, 18, 24, 24); layout.setSpacing(16)
        title = QLabel('Módulo de ventas'); title.setObjectName('dashboard_title'); layout.addWidget(title)
        subtitle = QLabel('Registra ventas y prepara cotizaciones. La información administrativa permanece protegida.')
        subtitle.setObjectName('dashboard_subtitle'); subtitle.setWordWrap(True); layout.addWidget(subtitle)
        card = QFrame(); card.setObjectName('pos_card'); card_layout = QVBoxLayout(card); card_layout.setContentsMargins(24, 24, 24, 24); card_layout.setSpacing(10)
        heading = QLabel('Atención al cliente'); heading.setObjectName('pos_card_title'); card_layout.addWidget(heading)
        for text, callback, style in (
                (NEW_SALE_LABEL, self.__presenter.open_sales_terminal, 'primary_pos_action'),
                (EXPRESS_SALE_LABEL, self.__presenter.open_express_sale, 'secondary_pos_action'),
                ('Crear cotización', self.__presenter.open_quote, 'secondary_pos_action'),
                (SALES_CHANNEL_LABEL, self.__presenter.open_sales_channel, 'secondary_pos_action')):
            button = QPushButton(text); button.setObjectName(style); button.clicked.connect(callback); card_layout.addWidget(button)
        layout.addWidget(card); layout.addStretch(); return dashboard

    def __get_dashboard_summary(self):
        fallback = {'sales': ZERO_MXN, 'operations': '0', 'expenses': ZERO_MXN,
                    'net_profit': ZERO_MXN, 'products': '0'}
        if hasattr(self.__presenter, 'get_dashboard_summary'):
            return self.__presenter.get_dashboard_summary()
        return fallback

    @staticmethod
    def __create_metric_card(caption, value):
        card = QFrame()
        card.setObjectName('metric_card')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 13, 16, 13)
        caption_label = QLabel(caption)
        caption_label.setObjectName('metric_caption')
        value_label = QLabel(value)
        value_label.setObjectName('metric_value')
        card_layout.addWidget(caption_label)
        card_layout.addWidget(value_label)
        return card

    def __create_sales_card(self):
        card = QFrame()
        card.setObjectName('pos_card')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        title = QLabel('Caja rápida')
        title.setObjectName('pos_card_title')
        description = QLabel('Registra ventas de forma ágil y consulta el catálogo sin salir de la operación.')
        description.setObjectName('dashboard_subtitle')
        description.setWordWrap(True)
        sell_button = QPushButton(NEW_SALE_LABEL)
        sell_button.setObjectName('primary_pos_action')
        sell_button.clicked.connect(self.__presenter.open_sales_terminal)
        inventory_button = QPushButton('Administrar inventario')
        inventory_button.setObjectName('secondary_pos_action')
        inventory_button.clicked.connect(self.__presenter.open_product_management)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()
        layout.addWidget(sell_button)
        layout.addWidget(inventory_button)
        return card

    def __create_quick_access_card(self, product_quantity):
        card = QFrame()
        card.setObjectName('pos_card')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        title = QLabel('Accesos rápidos')
        title.setObjectName('pos_card_title')
        stock = QLabel(f'{product_quantity} productos registrados en inventario')
        stock.setObjectName('dashboard_subtitle')
        expenses = QPushButton('Gastos operativos')
        expenses.setObjectName('secondary_pos_action')
        expenses.clicked.connect(self.__presenter.open_expense_management_presenter)
        reports = QPushButton('Ver reportes')
        reports.setObjectName('secondary_pos_action')
        reports.clicked.connect(lambda: self.__show_page(3))
        analysis = QPushButton('Ver análisis')
        analysis.setObjectName('secondary_pos_action')
        analysis.clicked.connect(lambda: self.__show_page(1))
        layout.addWidget(title)
        layout.addWidget(stock)
        layout.addSpacing(8)
        layout.addWidget(expenses)
        layout.addWidget(reports)
        layout.addWidget(analysis)
        layout.addStretch()
        return card

    def __apply_formal_iconography(self):
        """Unifica los accesos del inicio con iconos vectoriales de 72 px."""
        icon_map = {
            'label_3': 'eccos_inventory.svg',
            'label_7': 'eccos_expenses.svg',
            'label': REPORT_ICON,
            'label_2': REPORT_ICON,
            'label_4': REPORT_ICON,
            'label_5': REPORT_ICON,
            'label_6': REPORT_ICON,
            'label_8': 'eccos_analytics.svg',
            'label_9': 'eccos_analytics.svg',
        }
        for label_name, icon_name in icon_map.items():
            label = getattr(self, label_name)
            icon = QPixmap(resource_path(f'view/ui/images/{icon_name}'))
            label.setFixedSize(72, 72)
            label.setScaledContents(False)
            label.setPixmap(icon.scaled(
                64, 64, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

    def __show_page(self, page_index):
        self.__selected_page_index = page_index
        self.stacked_widget.setCurrentWidget(self.__pages_of_stacked_widget[page_index])

    def wire_up_gui_connections(self):
        self.product_management_button.clicked.connect(self.__presenter.open_product_management)
        self.day_report_button.clicked.connect(self.__presenter.open_day_sale_report_presenter)
        self.month_report_button.clicked.connect(self.__presenter.open_month_sale_report_presenter)
        self.year_report_button.clicked.connect(self.__presenter.open_year_sale_report_presenter)
        self.week_report_button.clicked.connect(self.__presenter.open_week_sale_report_presenter)
        self.custom_report_button.clicked.connect(self.__presenter.open_custom_sale_report_presenter)
        self.year_statistics_button.clicked.connect(self.__presenter.open_year_statistics_presenter)
        self.month_statistics_button.clicked.connect(self.__presenter.open_month_statistics_presenter)
        self.clicked_on_next_frame.connect(self.__show_next_page)
        self.clicked_on_previous_frame.connect(self.__show_previous_page)
        self.clicked_on_about_label.connect(self.__presenter.open_about_presenter)
        self.expenses_button.clicked.connect(self.__presenter.open_expense_management_presenter)

    def __show_next_page(self):
        self.__selected_page_index += 1
        if self.__selected_page_index == len(self.__pages_of_stacked_widget) - 1:
            self.next_frame.hide()
            self.previous_frame.show()
        else:
            self.next_frame.show()
            self.previous_frame.show()
        self.stacked_widget.setCurrentWidget(self.__pages_of_stacked_widget[self.__selected_page_index])
        self.__set_text_on_direction_frame_labels_depending_on_selected_page()

    def __set_text_on_direction_frame_labels_depending_on_selected_page(self):
        selected_page = self.__pages_of_stacked_widget[self.__selected_page_index]
        if selected_page == self.management_widget:
            self.previous_title_label.setText('Estadísticas')
            self.next_title_label.setText('Reportes')
        elif selected_page == self.statistics_widget:
            self.next_title_label.setText('Gestión')
        elif selected_page == self.reports_widget:
            self.previous_title_label.setText('Gestión')

    def __show_previous_page(self):
        self.__selected_page_index -= 1
        if self.__selected_page_index == 0:
            self.next_frame.show()
            self.previous_frame.hide()
        else:
            self.next_frame.show()
            self.previous_frame.show()
        self.stacked_widget.setCurrentWidget(self.__pages_of_stacked_widget[self.__selected_page_index])
        self.__set_text_on_direction_frame_labels_depending_on_selected_page()

    def mouseMoveEvent(self, event: QMouseEvent):
        self.__create_animations()
        self.__start_next_frame_animation_if_mouse_is_hovering()
        self.__start_previous_frame_animation_if_mouse_is_hovering()

    def __create_animations(self):
        if self.__next_frame_animation is None:
            self.__next_frame_animation = GoForwardAndReturnAnimation(
                self.next_frame, b'pos', 30, GoForwardAndReturnAnimation.RIGHT_DIRECTION)
            self.__next_frame_animation.finished.connect(
                self.__start_next_frame_animation_if_mouse_is_hovering
            )

        if self.__previous_frame_animation is None:
            self.__previous_frame_animation = GoForwardAndReturnAnimation(
                self.previous_frame, b'pos', 30, GoForwardAndReturnAnimation.LEFT_DIRECTION
            )
            self.__previous_frame_animation.finished.connect(
                self.__start_previous_frame_animation_if_mouse_is_hovering)

    def __start_next_frame_animation_if_mouse_is_hovering(self):
        if self.next_frame.underMouse() and (
                self.__next_frame_animation.state() == QPropertyAnimation.Stopped):
            self.__next_frame_animation.start()

    def __start_previous_frame_animation_if_mouse_is_hovering(self):
        if self.previous_frame.underMouse() and (
                self.__previous_frame_animation.state() == QPropertyAnimation.Stopped):
            self.__previous_frame_animation.start()

    def mouseReleaseEvent(self, mouse_event: QMouseEvent):
        if self.next_frame.underMouse():
            self.clicked_on_next_frame.emit()
        elif self.previous_frame.underMouse():
            self.clicked_on_previous_frame.emit()
        elif self.about_label.underMouse():
            self.clicked_on_about_label.emit()
