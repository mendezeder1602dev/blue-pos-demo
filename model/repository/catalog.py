import re
import unicodedata

from sqlalchemy import select

from model.entity.models import CatalogSettings, Product


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
