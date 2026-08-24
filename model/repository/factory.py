from model.repository.economic_summary import EconomicSummaryRepository
from model.repository.expense import ExpenseRepository
from model.repository.product import ProductRepository
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
import os
from pathlib import Path
from model.repository.sale import SaleRepository
from model.repository.sales_grouped_by_product import SalesGroupedByProductRepository
from model.repository.business_profile import BusinessProfileRepository
from model.repository.user import UserRepository
from model.repository.quote import QuoteRepository
from model.repository.cash_close import CashCloseRepository
from model.repository.cash_control import CashControlRepository


__BLUE_POS_FOLDER_PATH = Path(os.path.join(str(Path.home()), '.blue-pos/'))

if not __BLUE_POS_FOLDER_PATH.exists():
    __BLUE_POS_FOLDER_PATH.mkdir()

__BLUE_POS_DB_PATH = str(os.path.join(str(__BLUE_POS_FOLDER_PATH), 'data.db'))
__BLUE_POS_AUTH_DB_PATH = str(os.path.join(str(__BLUE_POS_FOLDER_PATH), 'accounts.db'))

DB_URL = f'sqlite:///{__BLUE_POS_DB_PATH}?check_same_thread=False'
AUTH_DB_URL = f'sqlite:///{__BLUE_POS_AUTH_DB_PATH}?check_same_thread=False'


class RepositoryFactory:
    __url = None
    __session: Session = None
    __product_repository = None
    __sale_repository = None
    __sales_grouped_by_product_repository = None
    __expense_repository = None
    __economic_summary_repository = None
    __engine = None
    __business_profile_repository = None
    __user_repository = None
    __auth_engine = None
    __auth_session = None
    __auth_user_repository = None
    __quote_repository = None
    __cash_close_repository = None
    __cash_control_repository = None

    @staticmethod
    def activate_workspace(url: str):
        """Cambia de espacio de trabajo y descarta repositorios de la sesión previa."""
        RepositoryFactory.__reset_workspace_session()
        RepositoryFactory.__create_session_if_necessary(url)

    @staticmethod
    def __reset_workspace_session():
        if RepositoryFactory.__session is not None:
            RepositoryFactory.__session.close()
        if RepositoryFactory.__engine is not None:
            RepositoryFactory.__engine.dispose()
        RepositoryFactory.__url = None
        RepositoryFactory.__session = None
        RepositoryFactory.__engine = None
        RepositoryFactory.__product_repository = None
        RepositoryFactory.__sale_repository = None
        RepositoryFactory.__sales_grouped_by_product_repository = None
        RepositoryFactory.__expense_repository = None
        RepositoryFactory.__economic_summary_repository = None
        RepositoryFactory.__business_profile_repository = None
        RepositoryFactory.__quote_repository = None
        RepositoryFactory.__cash_close_repository = None
        RepositoryFactory.__cash_control_repository = None

    @staticmethod
    def workspace_url(workspace_key: str) -> str:
        if not workspace_key or workspace_key == 'primary':
            return DB_URL
        safe_name = ''.join(char for char in workspace_key if char.isalnum() or char in ('-', '_'))
        return f"sqlite:///{__BLUE_POS_FOLDER_PATH / (safe_name + '.db')}?check_same_thread=False"

    @staticmethod
    def get_product_repository(url: str = None) -> ProductRepository:
        RepositoryFactory.__create_session_if_necessary(url)

        if RepositoryFactory.__product_repository is None:
            RepositoryFactory.__product_repository = ProductRepository(RepositoryFactory.__session)

        return RepositoryFactory.__product_repository

    @staticmethod
    def __create_session_if_necessary(db_url):
        # Sin URL explícita se conserva el espacio de trabajo activo. Esto es
        # esencial después de iniciar sesión en un workspace distinto.
        db_url = db_url or RepositoryFactory.__url or DB_URL
        if RepositoryFactory.__url != db_url:
            RepositoryFactory.__reset_workspace_session()
            RepositoryFactory.__url = db_url
            RepositoryFactory.__engine = create_engine(db_url, poolclass=NullPool)
            RepositoryFactory.__session = Session(RepositoryFactory.__engine)
        return RepositoryFactory.__session

    @staticmethod
    def get_sale_repository(url: str = None) -> SaleRepository:
        RepositoryFactory.__create_session_if_necessary(url)

        if RepositoryFactory.__sale_repository is None:
            RepositoryFactory.__sale_repository = SaleRepository(RepositoryFactory.__session)

        return RepositoryFactory.__sale_repository

    @staticmethod
    def get_expense_repository(url: str = None) -> ExpenseRepository:
        RepositoryFactory.__create_session_if_necessary(url)

        if RepositoryFactory.__expense_repository is None:
            RepositoryFactory.__expense_repository = ExpenseRepository(RepositoryFactory.__session)

        return RepositoryFactory.__expense_repository

    @staticmethod
    def get_sales_grouped_by_product_repository(url: str = None) -> SalesGroupedByProductRepository:
        RepositoryFactory.__create_session_if_necessary(url)

        if RepositoryFactory.__sales_grouped_by_product_repository is None:
            RepositoryFactory.__sales_grouped_by_product_repository = SalesGroupedByProductRepository(
                RepositoryFactory.__session)

        return RepositoryFactory.__sales_grouped_by_product_repository

    @staticmethod
    def get_economic_summary_repository(url: str = None):
        RepositoryFactory.__create_session_if_necessary(url)

        if RepositoryFactory.__economic_summary_repository is None:
            RepositoryFactory.__economic_summary_repository = EconomicSummaryRepository(
                RepositoryFactory.__session)

        return RepositoryFactory.__economic_summary_repository

    @staticmethod
    def get_business_profile_repository(url: str = None):
        RepositoryFactory.__create_session_if_necessary(url)
        if RepositoryFactory.__business_profile_repository is None:
            RepositoryFactory.__business_profile_repository = BusinessProfileRepository(RepositoryFactory.__session)
        return RepositoryFactory.__business_profile_repository

    @staticmethod
    def get_quote_repository(url: str = None):
        RepositoryFactory.__create_session_if_necessary(url)
        if RepositoryFactory.__quote_repository is None:
            RepositoryFactory.__quote_repository = QuoteRepository(RepositoryFactory.__session)
        return RepositoryFactory.__quote_repository

    @staticmethod
    def get_cash_close_repository(url: str = None):
        RepositoryFactory.__create_session_if_necessary(url)
        if RepositoryFactory.__cash_close_repository is None:
            RepositoryFactory.__cash_close_repository = CashCloseRepository(RepositoryFactory.__session)
        return RepositoryFactory.__cash_close_repository

    @staticmethod
    def get_cash_control_repository(url: str = None):
        RepositoryFactory.__create_session_if_necessary(url)
        if RepositoryFactory.__cash_control_repository is None:
            RepositoryFactory.__cash_control_repository = CashControlRepository(RepositoryFactory.__session)
        return RepositoryFactory.__cash_control_repository

    @staticmethod
    def get_user_repository():
        """Repositorio de credenciales separado de las ventas e inventario."""
        if RepositoryFactory.__auth_session is None:
            RepositoryFactory.__auth_engine = create_engine(AUTH_DB_URL, poolclass=NullPool)
            RepositoryFactory.__auth_session = Session(RepositoryFactory.__auth_engine)
            RepositoryFactory.__auth_user_repository = UserRepository(RepositoryFactory.__auth_session)
        return RepositoryFactory.__auth_user_repository

    @staticmethod
    def close_session():
        for session, engine in ((RepositoryFactory.__session, RepositoryFactory.__engine),
                                (RepositoryFactory.__auth_session, RepositoryFactory.__auth_engine)):
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
                bind = getattr(session, 'bind', None)
                if bind is not None:
                    try:
                        bind.dispose()
                    except Exception:
                        pass
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass

        RepositoryFactory.__url = None
        RepositoryFactory.__session = None
        RepositoryFactory.__engine = None
        RepositoryFactory.__product_repository = None
        RepositoryFactory.__sale_repository = None
        RepositoryFactory.__sales_grouped_by_product_repository = None
        RepositoryFactory.__expense_repository = None
        RepositoryFactory.__economic_summary_repository = None
        RepositoryFactory.__business_profile_repository = None
        RepositoryFactory.__quote_repository = None
        RepositoryFactory.__cash_close_repository = None
        RepositoryFactory.__cash_control_repository = None
        RepositoryFactory.__auth_session = None
        RepositoryFactory.__auth_engine = None
        RepositoryFactory.__auth_user_repository = None
