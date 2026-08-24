import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.entity.models import Base, Expense
from model.repository.expense import ExpenseRepository
from model.util.monetary_types import CUPMoney


class TestExpenseAdminWorkflow(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.repository = ExpenseRepository(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_expense_can_be_edited_and_archived(self):
        expense = Expense(name='Papelería', description='Compra inicial',
                          spent_money=CUPMoney('100.00'), date=date.today())
        self.repository.insert_expense(expense)

        self.repository.update_expense(Expense(
            id=expense.id, name='Papelería actualizada', description='Compra corregida',
            spent_money=CUPMoney('125.50'), date=date.today()))
        updated = self.repository.get_all_expenses()[0]
        self.assertEqual(updated.name, 'Papelería actualizada')
        self.assertEqual(float(updated.spent_money.amount), 125.50)

        self.repository.archive_expenses([updated.id])
        self.assertEqual(self.repository.get_all_expenses(), [])


if __name__ == '__main__':
    unittest.main()
