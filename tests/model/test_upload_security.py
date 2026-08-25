import unittest
from io import BytesIO

from PIL import Image

from model.upload_security import validate_image_upload


class UploadSecurityTest(unittest.TestCase):
    def test_rejects_file_with_fake_image_extension(self):
        with self.assertRaises(ValueError):
            validate_image_upload(b'no es una imagen', 1024, {'JPEG'})

    def test_accepts_real_png_and_reports_server_mime(self):
        output = BytesIO()
        Image.new('RGB', (20, 20), 'navy').save(output, format='PNG')
        content, mime = validate_image_upload(
            output.getvalue(), 20_000, {'PNG'})
        self.assertTrue(content.startswith(b'\x89PNG'))
        self.assertEqual(mime, 'image/png')

    def test_rejects_disallowed_real_format(self):
        output = BytesIO()
        Image.new('RGB', (20, 20), 'navy').save(output, format='PNG')
        with self.assertRaises(ValueError):
            validate_image_upload(output.getvalue(), 20_000, {'JPEG'})


if __name__ == '__main__':
    unittest.main()
