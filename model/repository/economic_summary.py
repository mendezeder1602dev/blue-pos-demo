from datetime import date, timedelta
from sqlalchemy.orm import Session
from model.entity.economic_summary import EconomicSummary
from sqlalchemy import case, func, cast, FLOAT, select

from model.entity.models import Sale, Expense
from model.util.monetary_types import CUPMoney


class EconomicSummaryRepository:
    """Calcula indicadores financieros en SQL para evitar cargar filas innecesarias."""

    def __init__(self, session: Session):
        self.__session = session

    def get_economic_summary_on_month(self, month_date: date) -> EconomicSummary:
        first_date_of_month = date(day=1, month=month_date.month, year=month_date.year)
        last_date_of_month = self.__get_last_date_of_month(month_date)

        return self.__construct_economic_summary(first_date_of_month, last_date_of_month)

    @staticmethod
    def __get_last_date_of_month(month_date: date):
        if month_date.month == 12:
            next_month = 1
        else:
            next_month = month_date.month + 1

        if next_month == 1:
            first_date_next_month = date(day=1, month=1, year=month_date.year + 1)
        else:
            first_date_next_month = date(day=1, month=next_month, year=month_date.year)

        return first_date_next_month - timedelta(days=1)

    def __construct_economic_summary(self, initial_date: date, final_date: date) -> EconomicSummary:
        row_derived_from_sales = self.__get_row_with_values_derived_from_sales(initial_date, final_date)
        total_expense_row = self.__get_total_expense_row(initial_date, final_date)

        acquired_money = row_derived_from_sales['acquired_money']
        acquired_money = CUPMoney(str(acquired_money)) if acquired_money is not None else CUPMoney('0.00')

        total_cost = row_derived_from_sales['total_cost']
        total_cost = CUPMoney(str(total_cost)) if total_cost is not None else CUPMoney('0.00')

        total_expense = total_expense_row['total_expense']
        total_expense = CUPMoney(str(total_expense)) if total_expense is not None else CUPMoney('0.00')

        total_profit = acquired_money - total_cost

        return EconomicSummary(
            initial_date=initial_date,
            final_date=final_date,
            sale_quantity=row_derived_from_sales['sale_quantity'],
            acquired_money=acquired_money,
            total_cost=total_cost,
            total_profit=total_profit,
            total_expense=total_expense,
            net_profit=total_profit - total_expense
        )

    def __get_row_with_values_derived_from_sales(self, initial_date: date, final_date: date):
        query = self.__construct_query_for_values_derived_from_sales(initial_date, final_date)
        return self.__session.execute(query).first()

    @staticmethod
    def __construct_query_for_values_derived_from_sales(initial_date: date, final_date: date):
        acquired_money = func.sum(cast(Sale.price, FLOAT)).label('acquired_money')
        total_cost = func.sum(cast(Sale.cost, FLOAT)).label('total_cost')
        sale_quantity = func.count(Sale.id).label('sale_quantity')

        query = select(acquired_money, total_cost, sale_quantity) \
            .where(Sale.date >= initial_date) \
            .where(Sale.date <= final_date) \
            .where(Sale.status != 'Anulada')
        return query

    def __get_total_expense_row(self, initial_date: date, final_date: date):
        total_expense = func.sum(cast(Expense.spent_money, FLOAT)).label('total_expense')
        return self.__session.execute(select(total_expense)
                                      .where(Expense.date >= initial_date)
                                      .where(Expense.date <= final_date)
                                      .where(Expense.is_active == True)).first()

    def get_economic_summary_on_day(self, day_date: date) -> EconomicSummary:
        return self.__construct_economic_summary(day_date, day_date)

    def get_daily_trend(self, initial_date: date, final_date: date) -> dict:
        """Resume un periodo por día con dos consultas, sin el patrón N+1.

        El resultado incluye días con ventas, gastos o ambos. La interfaz completa
        con ceros los días sin actividad para conservar una gráfica continua.
        """
        sale_rows = self.__session.execute(
            select(
                Sale.date.label('day'),
                func.sum(cast(Sale.price, FLOAT)).label('sales'),
                func.sum(cast(Sale.cost, FLOAT)).label('cost'),
                func.count(Sale.id).label('units'),
                func.count(func.distinct(Sale.transaction_id)).label('transactions'),
                func.sum(case((Sale.transaction_id.is_(None), 1), else_=0)).label('legacy'),
            )
            .where(Sale.date >= initial_date, Sale.date <= final_date,
                   Sale.status != 'Anulada')
            .group_by(Sale.date)
        ).all()
        expense_rows = self.__session.execute(
            select(
                Expense.date.label('day'),
                func.sum(cast(Expense.spent_money, FLOAT)).label('expenses'),
            )
            .where(Expense.date >= initial_date, Expense.date <= final_date,
                   Expense.is_active == True)
            .group_by(Expense.date)
        ).all()
        result = {
            row.day: {
                'sales': float(row.sales or 0), 'cost': float(row.cost or 0),
                'units': int(row.units or 0),
                'tickets': int(row.transactions or 0) + int(row.legacy or 0),
                'expenses': 0.0,
            }
            for row in sale_rows
        }
        for row in expense_rows:
            result.setdefault(row.day, {
                'sales': 0.0, 'cost': 0.0, 'units': 0, 'tickets': 0,
                'expenses': 0.0,
            })['expenses'] = float(row.expenses or 0)
        return result
