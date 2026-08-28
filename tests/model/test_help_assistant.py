import unittest

from model.help_assistant import find_answer, topics_for_role


class HelpAssistantTest(unittest.TestCase):
    def test_finds_topic_despite_missing_accents(self):
        topic = find_answer('como hago el corte de caja', 'seller')
        self.assertIsNotNone(topic)
        self.assertEqual(topic.page, 'Corte de caja')

    def test_does_not_expose_admin_topics_to_seller(self):
        questions = {topic.question for topic in topics_for_role('seller')}
        self.assertNotIn('¿Cómo registrar un retiro de efectivo?', questions)

    def test_unknown_question_returns_none(self):
        self.assertIsNone(find_answer('temperatura de marte', 'admin'))

    def test_new_operational_topics_are_searchable(self):
        scenarios = (
            ('como uso un vale con efectivo', 'Vales'),
            ('mi compra cuesta menos que el saldo del vale', 'Vales'),
            ('como reimprimo el ticket de 58 mm', 'Impresión'),
            ('como afecta el vale al corte de caja', 'Caja'),
        )
        for question, category in scenarios:
            with self.subTest(question=question):
                topic = find_answer(question, 'admin')
                self.assertIsNotNone(topic)
                self.assertEqual(topic.category, category)

    def test_administrator_sees_returns_and_voucher_support(self):
        questions = {topic.question for topic in topics_for_role('admin')}
        self.assertIn('¿Cómo se realiza una devolución parcial?', questions)
        self.assertIn('¿Cómo emitir un vale por una devolución?', questions)

    def test_seller_sees_payment_help_but_not_authorization_steps(self):
        questions = {topic.question for topic in topics_for_role('seller')}
        self.assertIn('¿Cómo cobro una compra utilizando un vale?', questions)
        self.assertIn('¿Puede el vendedor autorizar devoluciones o retiros?', questions)
        self.assertNotIn('¿Cómo emitir un vale por una devolución?', questions)


if __name__ == '__main__':
    unittest.main()
