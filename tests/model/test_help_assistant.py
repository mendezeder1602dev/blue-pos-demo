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


if __name__ == '__main__':
    unittest.main()
