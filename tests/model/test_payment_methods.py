import unittest

from model.payment_methods import normalize_enabled_payment_methods


class PaymentMethodsConfigurationTest(unittest.TestCase):
    def test_cash_is_always_kept_when_optional_methods_are_disabled(self):
        self.assertEqual(
            normalize_enabled_payment_methods('["Tarjeta"]'),
            ('Efectivo', 'Tarjeta'),
        )
        self.assertEqual(normalize_enabled_payment_methods('[]'), ('Efectivo',))

    def test_disabled_methods_stay_disabled_until_selected_again(self):
        stored = '["Efectivo", "Tarjeta"]'

        self.assertEqual(
            normalize_enabled_payment_methods(stored),
            ('Efectivo', 'Tarjeta'),
        )

    def test_missing_or_invalid_configuration_uses_all_methods_initially(self):
        self.assertEqual(
            normalize_enabled_payment_methods(''),
            ('Efectivo', 'Transferencia', 'Tarjeta', 'Crédito', 'Mixto', 'Vale'),
        )
        self.assertEqual(
            normalize_enabled_payment_methods('no es json'),
            ('Efectivo', 'Transferencia', 'Tarjeta', 'Crédito', 'Mixto', 'Vale'),
        )
