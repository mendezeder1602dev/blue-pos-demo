import json
import os
import unittest
from unittest.mock import patch

from model.online_support import (
    OnlineSupportError, ask_online_support, is_available, sanitize_question,
)


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            'choices': [{'message': {'content': 'Revisa el controlador de impresión.'}}]
        }).encode('utf-8')


class OnlineSupportTest(unittest.TestCase):
    def test_sanitizes_sensitive_identifiers(self):
        result = sanitize_question(
            'Vale VALE-ABCD-1234, venta V-000042, $5,300.00 MXN, '
            'correo cliente@example.com y teléfono 993 123 4567')
        self.assertNotIn('VALE-ABCD-1234', result)
        self.assertNotIn('V-000042', result)
        self.assertNotIn('5,300', result)
        self.assertNotIn('cliente@example.com', result)
        self.assertNotIn('993 123 4567', result)

    def test_reports_availability_only_with_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_available())
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test-key'}, clear=True):
            self.assertTrue(is_available())

    def test_requires_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(OnlineSupportError):
                ask_online_support('Mi impresora no responde', 'seller')

    def test_sends_only_sanitized_question(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured['body'] = json.loads(request.data.decode('utf-8'))
            captured['timeout'] = timeout
            return _FakeResponse()

        with patch.dict(os.environ, {'GROQ_API_KEY': 'test-key'}, clear=True), \
                patch('model.online_support.urlopen', side_effect=fake_urlopen):
            answer = ask_online_support(
                'No imprime el vale VALE-SECRET-1234 por $900.00 MXN', 'seller')

        sent = captured['body']['messages'][1]['content']
        self.assertEqual(answer, 'Revisa el controlador de impresión.')
        self.assertNotIn('VALE-SECRET-1234', sent)
        self.assertNotIn('$900.00', sent)
        self.assertEqual(captured['timeout'], 20)


if __name__ == '__main__':
    unittest.main()
