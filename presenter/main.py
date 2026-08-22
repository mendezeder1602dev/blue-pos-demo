from datetime import date
from types import SimpleNamespace

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from easy_mvp.abstract_presenter import AbstractPresenter
from easy_mvp.intent import Intent
from model import schema
from model.entity.models import Product, Sale
from model.repository.product import ProductFilter
from model.report.ticket import generate_ticket_pdf
from model.util.monetary_types import CUPMoney
from presenter.about import AboutPresenter
from presenter.custom_report import CustomSaleReportPresenter
from presenter.day_report import DaySaleReportPresenter
from presenter.expense_management import ExpenseManagementPresenter
from presenter.month_report import MonthSaleReportPresenter
from presenter.month_statistics import MonthStatisticsPresenter
from presenter.product_management import ProductManagementPresenter
from presenter.sales_terminal import SalesTerminalPresenter
from presenter.week_report import WeekSaleReportPresenter
from presenter.year_report import YearSaleReportPresenter
from presenter.year_statistics import YearStatisticsPresenter
from view.main import MainView
from view.login import LoginView
from model.repository.factory import RepositoryFactory
from view.style.blue import BLUE_STYLE
from view.operations import ExpressSaleDialog, QuoteDialog, BusinessProfileDialog, SalesChannelDialog


class MainPresenter(AbstractPresenter):

    def _on_initialize(self):
        self.__set_app_style()
        schema.create_auth_database()
        user = self.__authenticate_user()
        if user is None:
            QApplication.instance().quit()
            return
        self.__activate_user_workspace(user)
        self.__initialize_view()

    def __initialize_view(self):
        view = MainView(self, self.__active_user)
        self._set_view(view)

    def __activate_user_workspace(self, user):
        self.__active_user = user
        schema.activate_user_workspace(user)

    def __authenticate_user(self):
        users = RepositoryFactory.get_user_repository()

        def authenticate(username, password, selected_role):
            user = users.authenticate(username.strip(), password)
            if user is None:
                raise ValueError('Usuario o contraseña incorrectos.')
            if user.role != selected_role:
                raise ValueError('Selecciona el perfil asociado a esta cuenta.')
            return user

        def enter_seller():
            return SimpleNamespace(role='seller', display_name='Vendedor', workspace_key='primary')

        login = LoginView(authenticate, enter_seller, users.reset_password)
        return login.authenticated_user if login.exec_() else None

    def logout(self):
        """Cierra la sesión activa y vuelve al acceso sin cerrar la aplicación."""
        current_view = self.get_view()
        if current_view is not None:
            current_view.close()
        user = self.__authenticate_user()
        if user is None:
            QApplication.instance().quit()
            return
        self.__activate_user_workspace(user)
        self.__initialize_view()

    @staticmethod
    def __set_app_style():
        QApplication.instance().setStyleSheet(BLUE_STYLE)

    def on_window_closing(self):
        RepositoryFactory.close_session()

    def get_default_window_title(self) -> str:
        return 'Punto de Venta Grupo ECCOS'

    def is_administrator(self):
        return getattr(self.__active_user, 'role', '') == 'superuser'

    def __require_administrator(self):
        if not self.is_administrator():
            raise PermissionError('Esta función sólo está disponible para el administrador.')

    def get_business_profile_data(self) -> dict:
        profile = RepositoryFactory.get_business_profile_repository().get_profile()
        return {field: getattr(profile, field, '') or '' for field in (
            'business_name', 'owner_name', 'phone', 'address', 'whatsapp',
            'email', 'tax_id', 'website', 'logo_path')}

    def get_dashboard_summary(self) -> dict:
        """Resumen de turno para el tablero principal, usando los datos locales."""
        summary = RepositoryFactory.get_economic_summary_repository().get_economic_summary_on_day(date.today())
        product_quantity = len(RepositoryFactory.get_product_repository().get_all_products())

        def money_value(money):
            return f'{money.amount:,.2f} MXN'

        return {
            'sales': money_value(summary.acquired_money),
            'operations': str(summary.sale_quantity or 0),
            'expenses': money_value(summary.total_expense),
            'net_profit': money_value(summary.net_profit),
            'products': str(product_quantity),
        }

    LOW_STOCK_THRESHOLD = 5

    def get_low_stock_products(self) -> list:
        """Productos reales de inventario con pocas unidades restantes."""
        product_filter = ProductFilter()
        product_filter.less_than_quantity = self.LOW_STOCK_THRESHOLD
        products = RepositoryFactory.get_product_repository().get_products_by_filter(product_filter)
        return [{'name': product.name, 'quantity': product.quantity}
                for product in products if not product.is_temporary]

    def open_product_management(self):
        self.__require_administrator()
        intent = Intent(ProductManagementPresenter)
        self._open_other_presenter(intent)

    def open_sales_terminal(self):
        self._open_other_presenter(Intent(SalesTerminalPresenter))

    def open_express_sale(self):
        ExpressSaleDialog(self.register_express_sale, self.get_view(), allow_cost=self.is_administrator()).exec_()

    def register_express_sale(self, name, price, cost, quantity, add_to_inventory=True, generate_ticket=True):
        if not name:
            raise ValueError('Indica el nombre del artículo.')
        description = 'Artículo agregado desde venta rápida.' if add_to_inventory else 'Venta temporal: artículo ocasional.'
        product = Product(name=name, description=description,
                          price=CUPMoney(f'{price:.2f}'), cost=CUPMoney(f'{cost:.2f}'), quantity=quantity,
                          is_temporary=not add_to_inventory)
        products = RepositoryFactory.get_product_repository()
        products.insert_product(product)
        sale = Sale(product_id=product.id, price=product.price, cost=product.cost)
        new_sales = RepositoryFactory.get_sale_repository().insert_sales(sale, quantity)
        ticket_path = generate_ticket_pdf(
            self.get_business_profile_data(),
            [{'name': name, 'quantity': quantity, 'unit_price': price}],
            [a_sale.id for a_sale in new_sales], sale.date,
            'COMPROBANTE DE VENTA' if add_to_inventory else 'VENTA TEMPORAL',
        )
        if generate_ticket:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(ticket_path)))
        return (f'Venta registrada: {quantity} × {name}. Total: {price * quantity:,.2f} MXN\n'
                f'Ticket PDF: {ticket_path.name}')

    def open_quote(self):
        QuoteDialog(RepositoryFactory.get_business_profile_repository().get_profile(), self.get_view()).exec_()

    def open_sales_channel(self):
        SalesChannelDialog(self.get_view()).exec_()

    def open_business_profile(self):
        self.__require_administrator()
        repository = RepositoryFactory.get_business_profile_repository()
        dialog = BusinessProfileDialog(repository.get_profile(), repository.save_profile, self.get_view())
        if dialog.exec_():
            self.get_view().apply_business_profile(self.get_business_profile_data())

    def open_day_sale_report_presenter(self):
        self.__require_administrator()
        intent = Intent(DaySaleReportPresenter)
        self._open_other_presenter(intent)

    def open_month_sale_report_presenter(self):
        self.__require_administrator()
        intent = Intent(MonthSaleReportPresenter)
        self._open_other_presenter(intent)

    def open_year_sale_report_presenter(self):
        self.__require_administrator()
        intent = Intent(YearSaleReportPresenter)
        self._open_other_presenter(intent)

    def open_week_sale_report_presenter(self):
        self.__require_administrator()
        intent = Intent(WeekSaleReportPresenter)
        self._open_other_presenter(intent)

    def open_custom_sale_report_presenter(self):
        self.__require_administrator()
        intent = Intent(CustomSaleReportPresenter)
        self._open_other_presenter(intent)

    def open_about_presenter(self):
        intent = Intent(AboutPresenter)
        self._open_other_presenter(intent)

    def open_expense_management_presenter(self):
        self.__require_administrator()
        intent = Intent(ExpenseManagementPresenter)
        self._open_other_presenter(intent)

    def open_year_statistics_presenter(self):
        self.__require_administrator()
        intent = Intent(YearStatisticsPresenter)
        self._open_other_presenter(intent)

    def open_month_statistics_presenter(self):
        self.__require_administrator()
        intent = Intent(MonthStatisticsPresenter)
        self._open_other_presenter(intent)
