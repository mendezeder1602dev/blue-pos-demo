from sqlalchemy import select
from model.entity.models import BusinessProfile


class BusinessProfileRepository:
    def __init__(self, session):
        self.__session = session

    def get_profile(self):
        profile = self.__session.scalars(select(BusinessProfile)).first()
        if profile is None:
            profile = BusinessProfile()
            self.__session.add(profile)
            self.__session.commit()
        return profile

    def save_profile(self, values):
        profile = self.get_profile()
        for field, value in values.items():
            setattr(profile, field, value)
        self.__session.commit()
        return profile
