"""Hojas de estilo del sistema ECCOS, generadas desde los tokens de diseño.

Se exportan ``BLUE_STYLE`` (tema claro) y ``DARK_STYLE`` (tema oscuro) para no
romper los imports existentes; ``LIGHT_STYLE`` es un alias con el nombre nuevo.
Ambos temas salen de la misma plantilla, así que cualquier componente que se
añada queda cubierto en los dos sin duplicar reglas.
"""

from util.resources_path import resource_path
from view.style import tokens as t


def _build_style(c: dict, dark: bool) -> str:
    """Compone la hoja de estilo completa para una paleta de tema."""
    arrow = 'light' if dark else 'dark'
    return f'''
/* ------------------------------------------------------------------ base */
* {{
    font-family: {t.FONT_STACK};
    outline: none;
}}

QWidget, QFrame {{
    background: {c['canvas']};
    color: {c['ink']};
}}
QDialog {{ background: {c['canvas']}; }}
QLabel {{
    background: transparent;
    color: {c['ink']};
    font-size: {t.FONT_BODY};
}}
QToolTip {{
    background: {c['brand_deep']};
    border: 1px solid {c['border_strong']};
    border-radius: {t.RADIUS_SM};
    color: #FFFFFF;
    font-size: {t.FONT_SMALL};
    padding: 7px 10px;
}}
Line, QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    background: {c['border']};
    border: none;
    color: {c['border']};
    max-height: 1px;
}}

/* ---------------------------------------------------------- tipografía */
QLabel#management_label, QLabel#reports_label, QLabel#statistics_label {{
    color: {c['ink']};
    font-size: {t.FONT_H1};
    font-weight: {t.WEIGHT_BOLD};
    padding: 4px 0 10px 0;
}}
QLabel#section_eyebrow {{
    color: {c['ink_3']};
    font-size: {t.FONT_EYEBROW};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#section_title {{
    color: {c['ink']};
    font-size: {t.FONT_H2};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#section_help {{
    color: {c['ink_2']};
    font-size: {t.FONT_SMALL};
}}

/* ------------------------------------------------- navegación lateral */
/* Las reglas descendentes ganan a las de ID en QSS, así que todo lo que vive
   dentro del panel marino se declara con el prefijo del panel: de otro modo la
   transparencia heredada apagaría los acentos de marca. */
QFrame#side_navigation {{
    background: {c['brand_deep']};
    border: none;
}}
QFrame#side_navigation QWidget, QFrame#side_navigation QLabel {{ background: transparent; }}
QFrame#side_rail {{ background: transparent; }}
QFrame#side_navigation QLabel#side_brand {{
    color: #FFFFFF;
    font-size: {t.FONT_H3};
    font-weight: {t.WEIGHT_BOLD};
    padding: 0;
}}
QFrame#side_navigation QLabel#side_brand_sub {{
    color: {c['brass']};
    font-size: {t.FONT_EYEBROW};
    font-weight: {t.WEIGHT_SEMIBOLD};
    padding: 0;
}}
QFrame#side_navigation QLabel#side_section {{
    color: #7796B4;
    font-size: {t.FONT_EYEBROW};
    font-weight: {t.WEIGHT_BOLD};
    padding: 12px 10px 2px 10px;
}}
QFrame#side_navigation QLabel#side_caption {{
    color: #6E8CA8;
    font-size: {t.FONT_CAPTION};
    padding: 0 10px;
}}
QFrame#side_navigation QLabel#side_business_logo {{
    background: #14375A;
    border-radius: {t.RADIUS_MD};
    color: #FFFFFF;
    font-size: {t.FONT_H2};
    font-weight: {t.WEIGHT_BOLD};
}}
QFrame#side_navigation QFrame#side_divider {{ background: #1B3F60; max-height: 1px; }}
QToolButton#side_nav_button {{
    background: transparent;
    border: none;
    border-radius: {t.RADIUS_SM};
    color: #D6E4F1;
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_SEMIBOLD};
    padding: 9px 10px;
    text-align: left;
}}
QToolButton#side_nav_button:hover {{ background: #14375A; color: #FFFFFF; }}
QToolButton#side_nav_button:pressed {{ background: #0A2137; }}
QToolButton#side_nav_button:checked {{
    background: #17436C;
    color: #FFFFFF;
}}
QToolButton#side_nav_primary {{
    background: {c['primary']};
    border: none;
    border-radius: {t.RADIUS_SM};
    color: #FFFFFF;
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_BOLD};
    padding: 10px;
    text-align: left;
}}
QToolButton#side_nav_primary:hover {{ background: {c['primary_hover']}; }}
QFrame#side_navigation QFrame#side_user_chip {{
    background: #14375A;
    border: none;
    border-radius: {t.RADIUS_MD};
}}
QFrame#side_navigation QLabel#side_user_name {{
    color: #FFFFFF; font-size: {t.FONT_SMALL}; font-weight: {t.WEIGHT_BOLD};
}}
QFrame#side_navigation QLabel#side_user_role {{ color: #9DBBD6; font-size: {t.FONT_CAPTION}; }}
QFrame#side_navigation QLabel#side_user_avatar {{
    background: {c['primary']};
    border-radius: {t.RADIUS_SM};
    color: #FFFFFF;
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_BOLD};
}}

/* ---------------------------------------------------------- encabezado */
QFrame#page_header {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_LG};
}}
QFrame#page_header QLabel {{ background: transparent; }}
QLabel#dashboard_eyebrow {{
    color: {c['ink_3']};
    font-size: {t.FONT_EYEBROW};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#dashboard_title {{
    color: {c['ink']};
    font-size: {t.FONT_H1};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#dashboard_subtitle {{
    color: {c['ink_2']};
    font-size: {t.FONT_SMALL};
}}
QLabel#header_badge {{
    background: {c['primary_soft']};
    border-radius: {t.RADIUS_PILL};
    color: {c['primary']};
    font-size: {t.FONT_CAPTION};
    font-weight: {t.WEIGHT_BOLD};
    padding: 6px 14px;
}}

/* -------------------------------------------------------------- tarjetas */
QFrame#pos_card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_LG};
}}
QFrame#pos_card QLabel {{ background: transparent; }}
QLabel#pos_card_title {{
    color: {c['ink']};
    font-size: {t.FONT_H3};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#pos_card_help {{ color: {c['ink_2']}; font-size: {t.FONT_SMALL}; }}

QFrame#metric_card, QFrame#metric_card_sales, QFrame#metric_card_ops,
QFrame#metric_card_expense, QFrame#metric_card_profit {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_MD};
}}
QFrame#metric_card_sales {{ border-top: 3px solid {c['series_sales']}; }}
QFrame#metric_card_ops {{ border-top: 3px solid {c['ink_2']}; }}
QFrame#metric_card_expense {{ border-top: 3px solid {c['series_expense']}; }}
QFrame#metric_card_profit {{ border-top: 3px solid {c['series_profit']}; }}
QFrame#metric_card QLabel, QFrame#metric_card_sales QLabel, QFrame#metric_card_ops QLabel,
QFrame#metric_card_expense QLabel, QFrame#metric_card_profit QLabel {{ background: transparent; }}
QLabel#metric_caption {{
    color: {c['ink_3']};
    font-size: {t.FONT_EYEBROW};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#metric_value {{
    color: {c['ink']};
    font-size: {t.FONT_H2};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#metric_hint {{ color: {c['ink_3']}; font-size: {t.FONT_CAPTION}; }}

/* ------------------------------------------------- barras de la app */
QFrame#tool_bar_frame {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_MD};
}}
QFrame#main_content_frame {{ background: transparent; }}
QLabel#state_bar_label, QLabel#status_bar_label {{
    color: {c['ink_2']};
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_MEDIUM};
    padding: 2px;
}}
QLabel#filter_state_label {{
    color: {c['primary']};
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_SEMIBOLD};
}}

/* ------------------------------------------------ cifras de reportes */
QLabel#payment_money_label, QLabel#profit_money_label {{
    color: {c['ink']};
    font-size: {t.FONT_H3};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#total_cost_label, QLabel#expense_money_label {{
    color: {c['series_expense']};
    font-size: {t.FONT_H3};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#net_profit_label {{
    color: {c['series_profit'] if dark else '#12805A'};
    font-size: {t.FONT_H2};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#sale_quantity_label, QLabel#selected_quantity_label, QLabel#profit_value_label {{
    color: {c['ink']};
    font-size: {t.FONT_H3};
    font-weight: {t.WEIGHT_BOLD};
}}

/* ---------------------------------------------------------- formularios */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
    background: {c['surface']};
    border: 1px solid {c['border_strong']};
    border-radius: {t.RADIUS_SM};
    color: {c['ink']};
    font-size: {t.FONT_BODY};
    min-height: 30px;
    padding: 4px 10px;
    selection-background-color: {c['primary']};
    selection-color: #FFFFFF;
}}
QLineEdit#barcode_input {{
    background: {c['primary_soft']};
    border-color: {c['primary']};
    font-weight: {t.WEIGHT_SEMIBOLD};
}}
QPlainTextEdit, QTextEdit {{ min-height: 68px; }}
QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover,
QDateEdit:hover, QComboBox:hover {{ border-color: {c['ink_3']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
    border: 1px solid {c['primary']};
    background: {c['surface']};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QDateEdit:disabled, QComboBox:disabled {{
    background: {c['surface_sunken']};
    border-color: {c['border']};
    color: {c['disabled_ink']};
}}
QLineEdit:read-only {{ background: {c['surface_sunken']}; color: {c['ink_2']}; }}

QComboBox QAbstractItemView {{
    background: {c['surface']};
    border: 1px solid {c['border_strong']};
    border-radius: {t.RADIUS_SM};
    color: {c['ink']};
    padding: 4px;
    selection-background-color: {c['primary_soft']};
    selection-color: {c['ink']};
}}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QDateEdit::up-button {{
    border: none; width: 18px;
    image: url("{resource_path(f'view/ui/images/chevron_up_{arrow}.svg')}");
}}
QSpinBox::down-button, QDoubleSpinBox::down-button, QDateEdit::down-button {{
    border: none; width: 18px;
    image: url("{resource_path(f'view/ui/images/chevron_down_{arrow}.svg')}");
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url("{resource_path(f'view/ui/images/chevron_down_{arrow}.svg')}");
    width: 12px; height: 12px;
}}

/* ---------------------------------------------------------------- botones */
QPushButton {{
    background: {c['primary']};
    border: none;
    border-radius: {t.RADIUS_SM};
    color: #FFFFFF;
    font-size: {t.FONT_BODY};
    font-weight: {t.WEIGHT_SEMIBOLD};
    min-height: 34px;
    padding: 7px 18px;
}}
QPushButton:hover {{ background: {c['primary_hover']}; }}
QPushButton:pressed {{ background: {c['primary_pressed']}; }}
QPushButton:disabled {{ background: {c['disabled_bg']}; color: {c['disabled_ink']}; }}

QPushButton#primary_pos_action {{
    font-size: {t.FONT_BODY};
    font-weight: {t.WEIGHT_BOLD};
    min-height: 42px;
}}
QPushButton#secondary_pos_action, QPushButton#cancel_button {{
    background: {c['surface']};
    border: 1px solid {c['border_strong']};
    color: {c['ink']};
    font-weight: {t.WEIGHT_SEMIBOLD};
    min-height: 38px;
}}
QPushButton#secondary_pos_action:hover, QPushButton#cancel_button:hover {{
    background: {c['surface_hover']};
    border-color: {c['primary']};
    color: {c['primary']};
}}
QPushButton#dialog_delete_button {{ background: {c['danger']}; }}
QPushButton#dialog_delete_button:hover {{ background: {c['danger_hover']}; }}

QToolButton {{
    background: transparent;
    border: none;
    border-radius: {t.RADIUS_SM};
    color: {c['ink_2']};
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_SEMIBOLD};
    padding: 7px 10px;
}}
QToolButton:hover {{ background: {c['primary_soft']}; color: {c['primary']}; }}
QToolButton:pressed {{ background: {c['primary_soft_hover']}; }}
QToolButton:disabled {{ color: {c['disabled_ink']}; }}
QToolBar {{ background: transparent; border: none; spacing: 4px; }}

/* ----------------------------------------------------------------- tablas */
QTableWidget, QTableView {{
    background: {c['surface']};
    alternate-background-color: {c['surface_sunken']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_MD};
    color: {c['ink']};
    font-size: {t.FONT_SMALL};
    gridline-color: {c['grid']};
    selection-background-color: {c['primary_soft']};
    selection-color: {c['ink']};
}}
QTableWidget::item, QTableView::item {{ border: none; padding: 7px 8px; }}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {c['primary_soft']};
    color: {c['ink']};
}}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {c['surface_sunken']};
    border: none;
    border-bottom: 1px solid {c['border_strong']};
    color: {c['ink_3']};
    font-size: {t.FONT_CAPTION};
    font-weight: {t.WEIGHT_BOLD};
    padding: 10px 8px;
}}
QHeaderView::section:hover {{ color: {c['primary']}; }}
QTableCornerButton::section {{
    background: {c['surface_sunken']};
    border: none;
    border-bottom: 1px solid {c['border_strong']};
}}

/* ------------------------------------------------- grupos y selectores */
QGroupBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_MD};
    color: {c['ink']};
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_BOLD};
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
}}
QGroupBox::title {{
    color: {c['ink_3']};
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QFrame#analytics_header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['primary_soft']}, stop:1 {c['surface']});
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_LG};
}}
QLabel#analytics_title {{
    color: {c['ink']};
    font-size: {t.FONT_H3};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#analytics_insight {{
    color: {c['ink_2']};
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_MEDIUM};
}}
QFrame#analytics_kpi_sales, QFrame#analytics_kpi_profit,
QFrame#analytics_kpi_expense, QFrame#analytics_kpi_count {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_MD};
}}
QFrame#analytics_kpi_profit {{ border-top: 3px solid {c['series_profit']}; }}
QFrame#analytics_kpi_sales {{ border-top: 3px solid {c['series_sales']}; }}
QFrame#analytics_kpi_expense {{ border-top: 3px solid {c['series_expense']}; }}
QFrame#analytics_kpi_count {{ border-top: 3px solid {c['ink_2']}; }}
QLabel#analytics_metric_caption {{
    color: {c['ink_3']};
    font-size: {t.FONT_EYEBROW};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#analytics_metric_value {{
    color: {c['ink']};
    font-size: {t.FONT_H3};
    font-weight: {t.WEIGHT_BOLD};
}}

QCheckBox, QRadioButton {{
    background: transparent;
    color: {c['ink_2']};
    font-size: {t.FONT_SMALL};
    spacing: 8px;
}}
QCheckBox::indicator {{ width: 17px; height: 17px; }}
QCheckBox::indicator:unchecked {{ image: url("{resource_path('view/ui/images/unchecked.png')}"); }}
QCheckBox::indicator:checked {{ image: url("{resource_path('view/ui/images/checked.png')}"); }}
QRadioButton::indicator {{ width: 16px; height: 16px; }}
QRadioButton::indicator:unchecked {{ image: url("{resource_path('view/ui/images/unchecked_radio.png')}"); }}
QRadioButton::indicator:checked {{ image: url("{resource_path('view/ui/images/checked_radio.png')}"); }}

/* ------------------------------------------------------------ scrollbars */
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {c['scroll_handle']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['ink_3']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {c['scroll_handle']};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c['ink_3']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* -------------------------------------------------------------- portada */
QDialog#login_dialog {{ background: {c['surface']}; }}
QFrame#login_brand_panel {{
    background: qlineargradient(x1:0, y1:0, x2:0.9, y2:1,
        stop:0 {c['brand_deep']}, stop:1 {c['brand_mid']});
    border: none;
}}
QFrame#login_brand_panel QWidget, QFrame#login_brand_panel QLabel {{
    background: transparent;
    color: #FFFFFF;
}}
QFrame#login_brand_panel QLabel#login_brand_name {{
    font-size: {t.FONT_DISPLAY};
    font-weight: {t.WEIGHT_BOLD};
}}
QFrame#login_brand_panel QLabel#login_brand_rule {{ background: {c['brass']}; }}
QFrame#login_brand_panel QLabel#login_brand_product {{
    color: {c['brass']};
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_BOLD};
}}
QFrame#login_brand_panel QLabel#login_brand_tagline {{
    color: #C7DCEE;
    font-size: {t.FONT_H3};
    font-weight: {t.WEIGHT_MEDIUM};
}}
QFrame#login_brand_panel QLabel#login_brand_bullet {{
    color: #A8C6DE;
    font-size: {t.FONT_SMALL};
}}
QFrame#login_brand_panel QLabel#login_brand_marker {{
    background: {c['brass']};
    border-radius: 2px;
}}
QFrame#login_brand_panel QLabel#login_brand_footer {{
    color: #7A9CBB;
    font-size: {t.FONT_CAPTION};
}}
QFrame#login_access_panel {{ background: {c['surface']}; border: none; }}
QFrame#login_access_panel QLabel {{ background: transparent; }}
QLabel#login_heading {{
    color: {c['ink']};
    font-size: {t.FONT_H2};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#login_help {{ color: {c['ink_2']}; font-size: {t.FONT_SMALL}; }}
QFrame#login_profile_card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_MD};
}}
QFrame#login_profile_card:hover {{ border-color: {c['border_strong']}; }}
QFrame#login_profile_card[selected="true"] {{
    background: {c['primary_soft']};
    border: 1px solid {c['primary']};
}}
QFrame#login_profile_card QLabel {{ background: transparent; }}
QLabel#login_profile_name {{
    color: {c['ink']};
    font-size: {t.FONT_BODY};
    font-weight: {t.WEIGHT_BOLD};
}}
QLabel#login_profile_meta {{ color: {c['ink_2']}; font-size: {t.FONT_CAPTION}; }}
QPushButton#login_enter_button {{
    font-size: {t.FONT_BODY};
    font-weight: {t.WEIGHT_BOLD};
    min-height: 44px;
}}
QPushButton#login_link_button {{
    background: transparent;
    border: none;
    color: {c['primary']};
    font-size: {t.FONT_SMALL};
    font-weight: {t.WEIGHT_SEMIBOLD};
    padding: 8px 0;
    text-align: left;
}}
QPushButton#login_link_button:hover {{ color: {c['primary_hover']}; text-decoration: underline; }}
QRadioButton#login_role_radio {{
    background: {c['surface_sunken']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_SM};
    color: {c['ink_2']};
    font-size: {t.FONT_CAPTION};
    font-weight: {t.WEIGHT_SEMIBOLD};
    padding: 9px 7px;
}}
QRadioButton#login_role_radio:checked {{
    background: {c['primary_soft']};
    border-color: {c['primary']};
    color: {c['primary']};
}}
QRadioButton#login_role_radio::indicator {{ width: 0px; height: 0px; }}
QLabel#login_footer {{ color: {c['ink_3']}; font-size: {t.FONT_CAPTION}; }}

/* -------------------------------------------------------- cobro / venta */
QFrame#sale_checkout {{ background: {c['canvas']}; }}
QLabel#sale_checkout_business {{
    color: {c['primary']}; font-size: {t.FONT_EYEBROW}; font-weight: {t.WEIGHT_BOLD};
}}
QLabel#sale_checkout_title {{
    color: {c['ink']}; font-size: {t.FONT_H1}; font-weight: {t.WEIGHT_BOLD};
}}
QLabel#sale_checkout_help, QLabel#sale_checkout_note {{
    color: {c['ink_2']}; font-size: {t.FONT_SMALL};
}}
QFrame#sale_product_card {{
    background: {c['surface']}; border: 1px solid {c['border']}; border-radius: {t.RADIUS_MD};
}}
QFrame#sale_search_card, QFrame#sale_panel, QFrame#sale_payment_panel {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {t.RADIUS_MD};
}}
QFrame#sale_search_card QLabel, QFrame#sale_panel QLabel,
QFrame#sale_payment_panel QLabel {{ background: transparent; }}
QLabel#sale_panel_title {{
    color: {c['ink']};
    font-size: {t.FONT_BODY};
    font-weight: {t.WEIGHT_BOLD};
}}
QComboBox#sale_payment_method {{ min-height: 38px; }}
QFrame#sale_split_frame {{ background: transparent; border: none; }}
QFrame#sale_product_card QLabel {{ background: transparent; }}
QLabel#sale_product_name {{ color: {c['ink']}; font-size: {t.FONT_H3}; font-weight: {t.WEIGHT_BOLD}; }}
QLabel#sale_product_meta {{ color: {c['ink_2']}; font-size: {t.FONT_SMALL}; }}
QLabel#sale_field_label {{ color: {c['ink_2']}; font-size: {t.FONT_SMALL}; font-weight: {t.WEIGHT_SEMIBOLD}; }}
QSpinBox#sale_quantity_input {{ font-size: {t.FONT_H3}; font-weight: {t.WEIGHT_BOLD}; }}
QFrame#sale_total_card {{
    background: {c['brand_deep']}; border: none; border-radius: {t.RADIUS_MD};
}}
QFrame#sale_total_card QLabel {{ background: transparent; }}
QLabel#sale_total_caption {{ color: #C7DCEE; font-size: {t.FONT_SMALL}; font-weight: {t.WEIGHT_SEMIBOLD}; }}
QLabel#sale_total_value {{ color: #FFFFFF; font-size: {t.FONT_H1}; font-weight: {t.WEIGHT_BOLD}; }}
'''


BLUE_STYLE = _build_style(t.LIGHT, dark=False)
LIGHT_STYLE = BLUE_STYLE
DARK_STYLE = _build_style(t.DARK, dark=True)
