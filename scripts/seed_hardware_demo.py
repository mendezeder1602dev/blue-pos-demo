"""Carga datos de demostración para una ferretería en una base vacía de ECCOS."""
from datetime import date, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from model.entity.models import Base, Expense, Product, Sale
from model.repository.factory import DB_URL
from model.util.monetary_types import CUPMoney


PRODUCTS = (
    ('Martillo de uña 16 oz', 'Mango de fibra y cabeza de acero.', '850.00', '610.00', 28),
    ('Destornillador Phillips 6 in', 'Punta magnética de acero endurecido.', '320.00', '205.00', 42),
    ('Taladro percutor 1/2 in', 'Taladro eléctrico de 650 W.', '4800.00', '3650.00', 8),
    ('Caja de tornillos 1 1/2 in', 'Caja con 100 tornillos galvanizados.', '260.00', '155.00', 65),
    ('Cinta métrica 5 m', 'Cinta con carcasa reforzada y freno.', '410.00', '265.00', 31),
    ('Pintura blanca 1 galón', 'Pintura interior lavable.', '1250.00', '870.00', 19),
    ('Llave ajustable 10 in', 'Acero cromado para uso profesional.', '690.00', '470.00', 24),
    ('Juego de brocas x 13', 'Brocas para metal, madera y concreto.', '1100.00', '780.00', 15),
)


def seed_demo_data():
    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.scalar(select(func.count()).select_from(Product)):
            print('La base ya contiene productos; no se insertaron datos de demostración.')
            return False

        products = []
        for name, description, price, cost, quantity in PRODUCTS:
            product = Product(
                name=name, description=description, price=CUPMoney(price),
                cost=CUPMoney(cost), quantity=quantity,
            )
            products.append(product)
        session.add_all(products)
        session.flush()

        today = date.today()
        sales_plan = ((0, 3, 1), (1, 4, 2), (3, 5, 3), (4, 2, 4), (5, 2, 5), (6, 1, 7))
        for product_index, units, days_ago in sales_plan:
            product = products[product_index]
            product.quantity -= units
            for _ in range(units):
                session.add(Sale(
                    product_id=product.id, date=today - timedelta(days=days_ago),
                    price=product.price, cost=product.cost,
                ))

        session.add_all((
            Expense(name='Transporte de mercancía', description='Flete de proveedor local.',
                    spent_money=CUPMoney('780.00'), date=today - timedelta(days=6)),
            Expense(name='Electricidad del local', description='Consumo eléctrico semanal.',
                    spent_money=CUPMoney('420.00'), date=today - timedelta(days=3)),
            Expense(name='Material de empaque', description='Bolsas y etiquetas para entregas.',
                    spent_money=CUPMoney('235.00'), date=today - timedelta(days=1)),
        ))
        session.commit()
    print('Datos de demostración de ferretería creados: 8 productos, 17 ventas y 3 gastos.')
    return True


if __name__ == '__main__':
    seed_demo_data()
