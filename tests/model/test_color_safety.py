import unittest

from model.color_safety import (
    contrast_ratio,
    default_color_palette,
    ensure_contrast,
    normalize_hex_color,
    readable_text_color,
    suggested_color_palette,
)


class TestColorSafety(unittest.TestCase):
    def test_normalizes_hex_colors(self):
        self.assertEqual(normalize_hex_color('123abc'), '#123ABC')
        self.assertEqual(normalize_hex_color('#abcdef'), '#ABCDEF')
        self.assertEqual(normalize_hex_color('no-es-color', '#111820'), '#111820')

    def test_rejects_low_contrast_text(self):
        with self.assertRaises(ValueError):
            ensure_contrast('#FFFFFF', '#FFFFFF', 'Texto contra fondo')
        self.assertGreaterEqual(contrast_ratio('#111820', '#FFFFFF'), 4.5)

    def test_readable_text_color_chooses_best_option(self):
        self.assertEqual(readable_text_color('#FFFFFF'), '#111820')
        self.assertEqual(readable_text_color('#111820'), '#FFFFFF')

    def test_default_palette_uses_the_safe_application_defaults(self):
        self.assertEqual(default_color_palette(), {
            'brand_color': '#123B6D',
            'app_background_color': '#F1F3F6',
            'app_surface_color': '#FFFFFF',
            'app_text_color': '#111820',
            'document_primary_color': '#123B6D',
            'document_text_color': '#111820',
        })

    def test_suggested_palette_keeps_the_brand_and_creates_a_light_tint(self):
        palette = suggested_color_palette('#D62728')
        self.assertEqual(palette['brand_color'], '#D62728')
        self.assertEqual(palette['document_primary_color'], '#D62728')
        self.assertEqual(palette['app_surface_color'], '#FFFFFF')
        self.assertNotEqual(palette['app_background_color'], '#FFFFFF')
        self.assertGreaterEqual(
            contrast_ratio(palette['app_text_color'], palette['app_background_color']), 4.5)


if __name__ == '__main__':
    unittest.main()
