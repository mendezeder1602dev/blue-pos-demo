import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.entity.models import Base, Product
from model.repository.catalog import CatalogRepository, normalize_catalog_slug
from model.util.monetary_types import CUPMoney


class CatalogRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.repository = CatalogRepository(self.session)
        self.product = Product(
            name='Lápiz azul', description='Lápiz para escritura',
            price=CUPMoney('40.00'), cost=CUPMoney('20.00'), quantity=3)
        self.session.add(self.product)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_catalog_is_private_until_published(self):
        settings = self.repository.save_settings({
            'slug': 'Papelería Eder', 'is_published': False})
        self.assertEqual(settings.slug, 'papeleria-eder')
        self.assertIsNone(self.repository.get_published_by_slug(settings.slug))

        self.repository.save_settings({'is_published': True})
        self.assertIsNotNone(self.repository.get_published_by_slug(settings.slug))

    def test_only_explicitly_visible_products_are_returned(self):
        self.assertEqual(self.repository.get_catalog_products(), [])
        self.repository.save_product_presentation(self.product.id, {
            'catalog_visible': True, 'catalog_featured': True,
            'catalog_description': 'Ideal para la escuela.',
        })
        products = self.repository.get_catalog_products()
        self.assertEqual([product.name for product in products], ['Lápiz azul'])
        self.assertEqual(products[0].catalog_description, 'Ideal para la escuela.')

    def test_unknown_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.repository.save_product_presentation(self.product.id, {'cost': '0'})

    def test_slug_normalization(self):
        self.assertEqual(normalize_catalog_slug('  Mi Negocio 1602  '), 'mi-negocio-1602')


if __name__ == '__main__':
    unittest.main()
