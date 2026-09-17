from pathlib import Path


APP_SOURCE = Path('web/app.py').read_text(encoding='utf-8')


def test_recent_sales_exposes_detail_and_independent_pdf_download():
    assert "@st.dialog('Detalle de venta'" in APP_SOURCE
    assert "'Ver detalle'" in APP_SOURCE
    assert "'Descargar PDF de la venta'" in APP_SOURCE
    assert "sale_detail_pdf_sections" in APP_SOURCE


def test_recent_sales_cards_show_the_exact_sale_time():
    recent_sales_page = APP_SOURCE.split('def _render_recent_sales():', 1)[1]
    recent_sales_page = recent_sales_page.split(
        'def _render_inventory_excel_import', 1)[0]

    assert "detail['time_label']" in recent_sales_page
    assert "detail['date_label']" in recent_sales_page


def test_seller_activity_groups_sales_by_transaction_and_shows_time():
    dashboard = APP_SOURCE.split('def _render_seller_dashboard():', 1)[1]
    dashboard = dashboard.split('def _enabled_payment_methods', 1)[0]

    assert 'build_sale_detail' in dashboard
    assert "'Hora': detail['time_label']" in dashboard


def test_dashboard_today_sales_opens_history_filtered_to_today():
    dashboard_card = APP_SOURCE.split(
        'def _dashboard_sales_detail_card', 1)[1]
    dashboard_card = dashboard_card.split(
        'def _render_statistics_weekly_pulse', 1)[0]
    recent_sales_page = APP_SOURCE.split('def _render_recent_sales():', 1)[1]
    recent_sales_page = recent_sales_page.split(
        'def _render_inventory_excel_import', 1)[0]

    assert "callback_args=('Hoy',)" in dashboard_card
    assert "recent_sales_scope" in recent_sales_page
    assert "sale.date == mexico_today()" in recent_sales_page
