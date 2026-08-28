from sqlalchemy import select
from model.entity.models import BusinessProfile


class BusinessProfileRepository:
    EDITABLE_FIELDS = {
        'business_name', 'legal_name', 'business_type', 'slogan', 'owner_name',
        'phone', 'whatsapp', 'email', 'website', 'address', 'city', 'state',
        'postal_code', 'tax_id', 'tax_regime', 'receipt_header', 'receipt_footer',
        'return_policy', 'brand_color', 'logo_data', 'logo_mime',
    }
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
            if field not in self.EDITABLE_FIELDS:
                raise ValueError(f'El campo de perfil "{field}" no está permitido.')
            setattr(profile, field, value)
        self.__session.commit()
        return profile
