import ast
import unittest
from pathlib import Path


class HeldSaleCompletionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parents[1] / 'web' / 'app.py'
        ).read_text(encoding='utf-8')
        tree = ast.parse(cls.source)
        cls.functions = {
            node.name: ast.get_source_segment(cls.source, node)
            for node in tree.body if isinstance(node, ast.FunctionDef)
        }

    def test_completed_sale_cleanup_is_idempotent_and_removes_restored_wait(self):
        cleanup = self.functions['_finish_completed_pos_sale']

        self.assertIn("get('pos_restored_held_sale_id')", cleanup)
        self.assertIn('delete_held_sale(', cleanup)
        self.assertIn("pop('pos_restored_held_sale_id'", cleanup)
        self.assertIn("st.session_state['pos_sale_reset_pending'] = True", cleanup)
        self.assertIn('_clear_cart()', cleanup)

    def test_sales_page_repeats_cleanup_before_rendering_cart_widgets(self):
        sales = self.functions['_render_sales_content']

        pending_cleanup = sales.index("pop('pos_sale_reset_pending', False)")
        cart_initialization = sales.index("setdefault('pos_cart', {})")
        self.assertLess(pending_cleanup, cart_initialization)
        self.assertIn("st.session_state['pos_restored_held_sale_id'] = held.id", sales)
        self.assertIn('_finish_completed_pos_sale(active_register)', sales)

    def test_sales_page_uses_one_replaceable_screen_and_clears_it_after_charge(self):
        wrapper = self.functions['_render_sales']
        sales = self.functions['_render_sales_content']

        self.assertIn('sales_screen = st.empty()', wrapper)
        self.assertIn('with sales_screen.container():', wrapper)
        self.assertIn('_render_sales_content(sales_screen)', wrapper)
        cleanup = sales.index('_finish_completed_pos_sale(active_register)')
        clear_screen = sales.index('sales_screen.empty()', cleanup)
        rerun = sales.index('st.rerun()', clear_screen)
        self.assertLess(cleanup, clear_screen)
        self.assertLess(clear_screen, rerun)


if __name__ == '__main__':
    unittest.main()
