import re
import unicodedata

from sqlalchemy import Boolean, Column, Integer, String, Text, select

from model.entity import models as entity_models


Product = entity_models.Product


def _catalog_settings_model():
    """Tolera una recarga parcial de Streamlit Cloud durante cambios de esquema."""
    existing_model = getattr(entity_models, 'CatalogSettings', None)
    if existing_model is not None:
        return existing_model

    class CatalogSettings(entity_models.Base):
        __tablename__ = 'catalog_settings'
        id = Column(Integer, primary_key=True)
        slug = Column(String(length=80), nullable=False, unique=True, index=True,
                      default='mi-negocio')
        is_published = Column(Boolean, nullable=False, default=False)
        headline = Column(String(length=180), nullable=True, default='')
        about = Column(String(length=800), nullable=True, default='')
        whatsapp = Column(String(length=40), nullable=True, default='')
        business_hours = Column(String(length=300), nullable=True, default='')
        service_message = Column(String(length=300), nullable=True, default='')
        show_out_of_stock = Column(Boolean, nullable=False, default=True)

    entity_models.CatalogSettings = CatalogSettings
    return CatalogSettings


def _ensure_product_catalog_fields():
    field_definitions = {
        'catalog_visible': Column(Boolean, nullable=False, default=False, index=True),
        'catalog_featured': Column(Boolean, nullable=False, default=False),
        'catalog_description': Column(String(length=500), nullable=True, default=''),
        'catalog_image_data': Column(Text, nullable=True, default=''),
        'catalog_image_mime': Column(String(length=40), nullable=True, default=''),
    }
    for field_name, definition in field_definitions.items():
        if not hasattr(Product, field_name):
            setattr(Product, field_name, definition)


CatalogSettings = _catalog_settings_model()
_ensure_product_catalog_fields()


def normalize_catalog_slug(value):
    normalized = unicodedata.normalize('NFKD', (value or '').strip().lower())
    normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r'[^a-z0-9-]+', '-', normalized)
    return re.sub(r'-+', '-', slug).strip('-')


class CatalogRepository:
    SETTINGS_FIELDS = {
        'slug', 'is_published', 'headline', 'about', 'whatsapp',
        'business_hours', 'service_message', 'show_out_of_stock',
    }
    PRODUCT_FIELDS = {
        'catalog_visible', 'catalog_featured', 'catalog_description',
        'catalog_image_data', 'catalog_image_mime',
    }

    def __init__(self, session):
        self.__session = session

    def get_settings(self):
        settings = self.__session.scalars(select(CatalogSettings)).first()
        if settings is None:
            settings = CatalogSettings()
            self.__session.add(settings)
            self.__session.commit()
        return settings

    def get_published_by_slug(self, slug):
        clean_slug = normalize_catalog_slug(slug)
        return self.__session.scalar(select(CatalogSettings).where(
            CatalogSettings.slug == clean_slug,
            CatalogSettings.is_published == True,
        ))

    def save_settings(self, values):
        unknown = set(values) - self.SETTINGS_FIELDS
        if unknown:
            raise ValueError(f'Campos de catálogo no permitidos: {", ".join(sorted(unknown))}.')
        settings = self.get_settings()
        for field, value in values.items():
            if field == 'slug':
                value = normalize_catalog_slug(value)
                if len(value) < 3:
                    raise ValueError('La dirección del catálogo debe tener al menos 3 caracteres.')
            setattr(settings, field, value)
        self.__session.commit()
        return settings

    def save_product_presentation(self, product_id, values):
        unknown = set(values) - self.PRODUCT_FIELDS
        if unknown:
            raise ValueError(f'Campos de producto no permitidos: {", ".join(sorted(unknown))}.')
        product = self.__session.get(Product, int(product_id))
        if product is None or not product.is_active or product.is_temporary:
            raise ValueError('El producto ya no está disponible.')
        for field, value in values.items():
            setattr(product, field, value)
        self.__session.commit()
        return product

    def get_catalog_products(self):
        return list(self.__session.scalars(select(Product).where(
            Product.is_active == True,
            Product.is_temporary == False,
            Product.catalog_visible == True,
        ).order_by(Product.catalog_featured.desc(), Product.name)).all())
