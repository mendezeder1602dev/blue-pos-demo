from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from model.entity.models import Quote


class QuoteRepository:
    def __init__(self, session: Session):
        self.__session = session

    def insert_quote(self, quote: Quote):
        if not quote.items:
            raise ValueError('Agrega al menos un artículo a la cotización.')
        if any(item.quantity <= 0 or item.unit_price.amount <= 0 for item in quote.items):
            raise ValueError('Las cantidades y precios deben ser mayores que cero.')
        self.__session.add(quote)
        self.__session.commit()

    def get_all_quotes(self):
        return self.__session.scalars(
            select(Quote).options(selectinload(Quote.items)).order_by(Quote.id.desc())
        ).all()

    def update_status(self, quote_id: int, status: str):
        quote = self.__session.get(Quote, quote_id)
        if quote is None:
            raise ValueError('La cotización ya no existe.')
        quote.status = status
        self.__session.commit()

    def delete_quote(self, quote_id: int):
        quote = self.__session.get(Quote, quote_id)
        if quote is not None:
            self.__session.delete(quote)
            self.__session.commit()
