from sqlalchemy import select

from model.color_safety import (
    DEFAULT_APP_BACKGROUND,
    DEFAULT_APP_SURFACE,
    DEFAULT_APP_TEXT,
    DEFAULT_BRAND_COLOR,
    DEFAULT_DOCUMENT_TEXT,
    ensure_contrast,
    normalize_hex_color,
)
from model.entity.models import BusinessProfile


class BusinessProfileRepository:
    EDITABLE_FIELDS = {
        'business_name', 'legal_name', 'business_type', 'slogan', 'owner_name',
        'phone', 'whatsapp', 'email', 'website', 'address', 'city', 'state',
        'postal_code', 'tax_id', 'tax_regime', 'receipt_header', 'receipt_footer',
        'return_policy', 'brand_color', 'app_background_color', 'app_surface_color',
        'app_text_color', 'document_primary_color', 'document_text_color',
        'logo_data', 'logo_mime',
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
        values = dict(values)
        color_defaults = {
            'brand_color': DEFAULT_BRAND_COLOR,
            'app_background_color': DEFAULT_APP_BACKGROUND,
            'app_surface_color': DEFAULT_APP_SURFACE,
            'app_text_color': DEFAULT_APP_TEXT,
            'document_primary_color': (
                values.get('brand_color') or profile.brand_color or DEFAULT_BRAND_COLOR
            ),
            'document_text_color': DEFAULT_DOCUMENT_TEXT,
        }
        for field, fallback in color_defaults.items():
            if field in values:
                values[field] = normalize_hex_color(values[field], fallback)

        app_text = values.get('app_text_color') or profile.app_text_color or DEFAULT_APP_TEXT
        app_background = (
            values.get('app_background_color')
            or profile.app_background_color
            or DEFAULT_APP_BACKGROUND
        )
        app_surface = values.get('app_surface_color') or profile.app_surface_color or DEFAULT_APP_SURFACE
        document_text = values.get('document_text_color') or profile.document_text_color or DEFAULT_DOCUMENT_TEXT
        ensure_contrast(app_text, app_background, 'Texto principal contra fondo de la app')
        ensure_contrast(app_text, app_surface, 'Texto principal contra tarjetas de la app')
        ensure_contrast(document_text, '#FFFFFF', 'Texto de documentos contra fondo blanco')
        for field, value in values.items():
            if field not in self.EDITABLE_FIELDS:
                raise ValueError(f'El campo de perfil "{field}" no está permitido.')
            setattr(profile, field, value)
        self.__session.commit()
        return profile
